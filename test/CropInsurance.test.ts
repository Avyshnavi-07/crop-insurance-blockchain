import { expect } from "chai";
import { ethers } from "hardhat";
import { time } from "@nomicfoundation/hardhat-network-helpers";
import { CropInsurance, MaliciousAttacker } from "../typechain-types";
import { HardhatEthersSigner } from "@nomicfoundation/hardhat-ethers/signers";

describe("CropInsurance Smart Contract Test Suite", function () {
  let cropInsurance: CropInsurance;
  let admin: HardhatEthersSigner;
  let oracleWeather: HardhatEthersSigner;
  let oracleSatellite: HardhatEthersSigner;
  let oracleSoil: HardhatEthersSigner;
  let fraudChecker: HardhatEthersSigner;
  let disputeReviewer: HardhatEthersSigner;
  let farmer1: HardhatEthersSigner;
  let farmer2: HardhatEthersSigner;
  let unauthorized: HardhatEthersSigner;

  // Severity Tier Enum
  const TIER_0 = 0; // Normal (0%)
  const TIER_1 = 1; // Moderate (25%)
  const TIER_2 = 2; // Severe (50%)
  const TIER_3 = 3; // Catastrophic (100%)

  // Policy Status Enum
  const STATUS_ACTIVE = 0;
  const STATUS_SETTLED = 1;
  const STATUS_UNDER_REVIEW = 2;

  // Oracle Source Enum
  const SOURCE_WEATHER = 0;
  const SOURCE_SATELLITE = 1;
  const SOURCE_SOIL = 2;

  // Crop & Region Enums
  const CROP_GROUNDNUT = 0;
  const REGION_ANANTAPUR = 0; // Base 3% + 3.5% = 6.5% premium
  const REGION_KURNOOL = 1; // Base 3% + 2.5% = 5.5% premium
  const REGION_KADAPA = 2; // Base 3% + 2.0% = 5.0% premium

  const DUMMY_RULES_HASH = ethers.keccak256(ethers.toUtf8Bytes("tier_rules_v1.0.0"));
  const DUMMY_LAND_1 = ethers.keccak256(ethers.toUtf8Bytes("land_parcel_anantapur_001"));
  const DUMMY_LAND_2 = ethers.keccak256(ethers.toUtf8Bytes("land_parcel_kurnool_002"));

  const SUM_INSURED = ethers.parseEther("1.0"); // 1 ETH sum insured

  beforeEach(async function () {
    [
      admin,
      oracleWeather,
      oracleSatellite,
      oracleSoil,
      fraudChecker,
      disputeReviewer,
      farmer1,
      farmer2,
      unauthorized,
    ] = await ethers.getSigners();

    const CropInsuranceFactory = await ethers.getContractFactory("CropInsurance");
    cropInsurance = await CropInsuranceFactory.deploy(admin.address);
    await cropInsurance.waitForDeployment();

    // Grant roles
    await cropInsurance.grantRole(await cropInsurance.ORACLE_WEATHER_ROLE(), oracleWeather.address);
    await cropInsurance.grantRole(
      await cropInsurance.ORACLE_SATELLITE_ROLE(),
      oracleSatellite.address
    );
    await cropInsurance.grantRole(await cropInsurance.ORACLE_SOIL_ROLE(), oracleSoil.address);
    await cropInsurance.grantRole(await cropInsurance.FRAUD_CHECKER_ROLE(), fraudChecker.address);
    await cropInsurance.grantRole(
      await cropInsurance.DISPUTE_REVIEWER_ROLE(),
      disputeReviewer.address
    );

    // Initial Risk Pool Funding: 10 ETH
    await cropInsurance.connect(admin).fundRiskPool({ value: ethers.parseEther("10.0") });
  });

  describe("1. Deployment & Pool Solvency Verification", function () {
    it("should initialize with correct roles, rates, and funded balance", async function () {
      expect(await cropInsurance.hasRole(await cropInsurance.DEFAULT_ADMIN_ROLE(), admin.address))
        .to.be.true;
      expect(await cropInsurance.regionalRiskBps(REGION_ANANTAPUR)).to.equal(350);
      expect(await cropInsurance.regionalRiskBps(REGION_KURNOOL)).to.equal(250);
      expect(await cropInsurance.regionalRiskBps(REGION_KADAPA)).to.equal(200);
      expect(await cropInsurance.riskPoolBalance()).to.equal(ethers.parseEther("10.0"));
      expect(await cropInsurance.reservedExposure()).to.equal(0);
    });

    it("should calculate correct premium with regional risk additions", async function () {
      // Anantapur: 300 + 350 = 650 bps (6.5%)
      const premAnantapur = await cropInsurance.calculatePremium(SUM_INSURED, REGION_ANANTAPUR);
      expect(premAnantapur).to.equal(ethers.parseEther("0.065"));

      // Kurnool: 300 + 250 = 550 bps (5.5%)
      const premKurnool = await cropInsurance.calculatePremium(SUM_INSURED, REGION_KURNOOL);
      expect(premKurnool).to.equal(ethers.parseEther("0.055"));

      // Kadapa: 300 + 200 = 500 bps (5.0%)
      const premKadapa = await cropInsurance.calculatePremium(SUM_INSURED, REGION_KADAPA);
      expect(premKadapa).to.equal(ethers.parseEther("0.050"));
    });

    it("should revert policy creation if risk pool cannot cover total exposure", async function () {
      // Deploy fresh contract with zero pool
      const CropInsuranceFactory = await ethers.getContractFactory("CropInsurance");
      const emptyInsurance = await CropInsuranceFactory.deploy(admin.address);
      await emptyInsurance.waitForDeployment();

      const premium = await emptyInsurance.calculatePremium(SUM_INSURED, REGION_ANANTAPUR);
      const currentTime = await time.latest();

      // Policy requires SUM_INSURED (1 ETH) backing, but pool only gets 0.065 ETH
      await expect(
        emptyInsurance
          .connect(farmer1)
          .createPolicy(
            DUMMY_LAND_1,
            CROP_GROUNDNUT,
            REGION_ANANTAPUR,
            SUM_INSURED,
            currentTime,
            currentTime + 3600,
            DUMMY_RULES_HASH,
            { value: premium }
          )
      ).to.be.revertedWithCustomError(emptyInsurance, "InsufficientRiskPool");
    });
  });

  describe("2. Policy Creation & Duplicate Land Guard", function () {
    it("should create a valid policy and track exposure", async function () {
      const premium = await cropInsurance.calculatePremium(SUM_INSURED, REGION_ANANTAPUR);
      const currentTime = await time.latest();
      const startTime = currentTime + 10;
      const endTime = currentTime + 1000;

      await expect(
        cropInsurance
          .connect(farmer1)
          .createPolicy(
            DUMMY_LAND_1,
            CROP_GROUNDNUT,
            REGION_ANANTAPUR,
            SUM_INSURED,
            startTime,
            endTime,
            DUMMY_RULES_HASH,
            { value: premium }
          )
      )
        .to.emit(cropInsurance, "PolicyCreated")
        .withArgs(
          1,
          farmer1.address,
          DUMMY_LAND_1,
          REGION_ANANTAPUR,
          CROP_GROUNDNUT,
          SUM_INSURED,
          premium,
          startTime,
          endTime,
          DUMMY_RULES_HASH
        );

      expect(await cropInsurance.activeLandHashes(DUMMY_LAND_1)).to.be.true;
      expect(await cropInsurance.reservedExposure()).to.equal(SUM_INSURED);
      expect(await cropInsurance.riskPoolBalance()).to.equal(ethers.parseEther("10.0") + premium);
    });

    it("should revert if incorrect premium is sent", async function () {
      const currentTime = await time.latest();
      await expect(
        cropInsurance.connect(farmer1).createPolicy(
          DUMMY_LAND_1,
          CROP_GROUNDNUT,
          REGION_ANANTAPUR,
          SUM_INSURED,
          currentTime + 10,
          currentTime + 1000,
          DUMMY_RULES_HASH,
          { value: ethers.parseEther("0.01") } // Wrong premium
        )
      ).to.be.revertedWithCustomError(cropInsurance, "IncorrectPremiumPaid");
    });

    it("should prevent duplicate active policies for the same land parcel", async function () {
      const premium = await cropInsurance.calculatePremium(SUM_INSURED, REGION_ANANTAPUR);
      const currentTime = await time.latest();

      await cropInsurance
        .connect(farmer1)
        .createPolicy(
          DUMMY_LAND_1,
          CROP_GROUNDNUT,
          REGION_ANANTAPUR,
          SUM_INSURED,
          currentTime + 10,
          currentTime + 1000,
          DUMMY_RULES_HASH,
          { value: premium }
        );

      // Attempt by farmer2 to insure the same land parcel
      await expect(
        cropInsurance
          .connect(farmer2)
          .createPolicy(
            DUMMY_LAND_1,
            CROP_GROUNDNUT,
            REGION_ANANTAPUR,
            SUM_INSURED,
            currentTime + 10,
            currentTime + 1000,
            DUMMY_RULES_HASH,
            { value: premium }
          )
      ).to.be.revertedWithCustomError(cropInsurance, "LandAlreadyInsured");
    });
  });

  describe("3. Oracle Submission Rules & Access Control", function () {
    let policyId: number;
    let endTime: number;

    beforeEach(async function () {
      const premium = await cropInsurance.calculatePremium(SUM_INSURED, REGION_ANANTAPUR);
      const currentTime = await time.latest();
      endTime = currentTime + 1000;

      const tx = await cropInsurance
        .connect(farmer1)
        .createPolicy(
          DUMMY_LAND_1,
          CROP_GROUNDNUT,
          REGION_ANANTAPUR,
          SUM_INSURED,
          currentTime + 10,
          endTime,
          DUMMY_RULES_HASH,
          { value: premium }
        );
      await tx.wait();
      policyId = 1;
    });

    it("should revert if oracle reports before season end", async function () {
      await expect(
        cropInsurance.connect(oracleWeather).submitReport(policyId, SOURCE_WEATHER, TIER_1)
      ).to.be.revertedWithCustomError(cropInsurance, "SeasonNotEnded");
    });

    it("should revert if unauthorized account submits oracle report", async function () {
      await time.increaseTo(endTime + 1);

      await expect(
        cropInsurance.connect(unauthorized).submitReport(policyId, SOURCE_WEATHER, TIER_1)
      ).to.be.revertedWithCustomError(cropInsurance, "UnauthorizedOracleSource");
    });

    it("should revert if the same oracle submits duplicate reports", async function () {
      await time.increaseTo(endTime + 1);

      await cropInsurance.connect(oracleWeather).submitReport(policyId, SOURCE_WEATHER, TIER_1);

      await expect(
        cropInsurance.connect(oracleWeather).submitReport(policyId, SOURCE_WEATHER, TIER_2)
      ).to.be.revertedWithCustomError(cropInsurance, "OracleAlreadyReported");
    });
  });

  describe("4. Consensus Logic & Payout Calculations", function () {
    let policyId: number;
    let endTime: number;

    beforeEach(async function () {
      const premium = await cropInsurance.calculatePremium(SUM_INSURED, REGION_ANANTAPUR);
      const currentTime = await time.latest();
      endTime = currentTime + 1000;

      await cropInsurance
        .connect(farmer1)
        .createPolicy(
          DUMMY_LAND_1,
          CROP_GROUNDNUT,
          REGION_ANANTAPUR,
          SUM_INSURED,
          currentTime + 10,
          endTime,
          DUMMY_RULES_HASH,
          { value: premium }
        );
      policyId = 1;
      await time.increaseTo(endTime + 1);
    });

    it("should revert settlement if only one report is submitted", async function () {
      await cropInsurance.connect(oracleWeather).submitReport(policyId, SOURCE_WEATHER, TIER_2);

      await expect(cropInsurance.settlePolicy(policyId)).to.be.revertedWithCustomError(
        cropInsurance,
        "ConsensusNotReached"
      );
    });

    it("should revert settlement if only two reports exist and they disagree", async function () {
      await cropInsurance.connect(oracleWeather).submitReport(policyId, SOURCE_WEATHER, TIER_1);
      await cropInsurance.connect(oracleSatellite).submitReport(policyId, SOURCE_SATELLITE, TIER_2);

      // 2 reports disagree: contract waits for the 3rd oracle
      await expect(cropInsurance.settlePolicy(policyId)).to.be.revertedWithCustomError(
        cropInsurance,
        "ConsensusNotReached"
      );
    });

    it("should settle when two reports agree (2-of-3 consensus) without waiting for 3rd", async function () {
      await cropInsurance.connect(oracleWeather).submitReport(policyId, SOURCE_WEATHER, TIER_2);
      await cropInsurance.connect(oracleSatellite).submitReport(policyId, SOURCE_SATELLITE, TIER_2);

      await expect(cropInsurance.settlePolicy(policyId))
        .to.emit(cropInsurance, "PolicySettled")
        .withArgs(policyId, TIER_2, ethers.parseEther("0.5"), STATUS_SETTLED);

      const policy = await cropInsurance.policies(policyId);
      expect(policy.status).to.equal(STATUS_SETTLED);
      expect(policy.finalTier).to.equal(TIER_2);
      expect(policy.payoutAmount).to.equal(ethers.parseEther("0.5")); // 50% for Tier 2

      // Land hash should now be freed for future seasons
      expect(await cropInsurance.activeLandHashes(DUMMY_LAND_1)).to.be.false;
      // Farmer claimable balance should be credited
      expect(await cropInsurance.claimableBalance(farmer1.address)).to.equal(
        ethers.parseEther("0.5")
      );
    });

    it("should correctly resolve median when all three oracles differ", async function () {
      // Oracles report Tier 0, Tier 2, Tier 1 -> Median is Tier 1 (25% payout)
      await cropInsurance.connect(oracleWeather).submitReport(policyId, SOURCE_WEATHER, TIER_0);
      await cropInsurance.connect(oracleSatellite).submitReport(policyId, SOURCE_SATELLITE, TIER_2);
      await cropInsurance.connect(oracleSoil).submitReport(policyId, SOURCE_SOIL, TIER_1);

      await cropInsurance.settlePolicy(policyId);

      const policy = await cropInsurance.policies(policyId);
      expect(policy.finalTier).to.equal(TIER_1); // Median of {0, 1, 2} is 1
      expect(policy.payoutAmount).to.equal(ethers.parseEther("0.25")); // 25% payout
    });

    it("should verify happy path payout amounts for all tiers (0%, 25%, 50%, 100%)", async function () {
      expect(await cropInsurance.calculatePayout(SUM_INSURED, TIER_0)).to.equal(0);
      expect(await cropInsurance.calculatePayout(SUM_INSURED, TIER_1)).to.equal(
        ethers.parseEther("0.25")
      );
      expect(await cropInsurance.calculatePayout(SUM_INSURED, TIER_2)).to.equal(
        ethers.parseEther("0.50")
      );
      expect(await cropInsurance.calculatePayout(SUM_INSURED, TIER_3)).to.equal(
        ethers.parseEther("1.00")
      );
    });
  });

  describe("5. Fraud Flag Hook & Timeout Escalation", function () {
    let policyId: number;
    let endTime: number;

    beforeEach(async function () {
      const premium = await cropInsurance.calculatePremium(SUM_INSURED, REGION_ANANTAPUR);
      const currentTime = await time.latest();
      endTime = currentTime + 1000;

      await cropInsurance
        .connect(farmer1)
        .createPolicy(
          DUMMY_LAND_1,
          CROP_GROUNDNUT,
          REGION_ANANTAPUR,
          SUM_INSURED,
          currentTime + 10,
          endTime,
          DUMMY_RULES_HASH,
          { value: premium }
        );
      policyId = 1;
    });

    it("should allow fraud checker to flag policy before payout and halt settlement", async function () {
      await time.increaseTo(endTime + 1);
      await cropInsurance.connect(oracleWeather).submitReport(policyId, SOURCE_WEATHER, TIER_3);
      await cropInsurance.connect(oracleSatellite).submitReport(policyId, SOURCE_SATELLITE, TIER_3);

      const fraudReason = ethers.keccak256(
        ethers.toUtf8Bytes("SYNTHETIC_ANOMALOUS_PARCEL_OVERLAP")
      );

      // Fraud checker flags policy
      await expect(cropInsurance.connect(fraudChecker).flagFraud(policyId, fraudReason))
        .to.emit(cropInsurance, "PolicyFlaggedFraud")
        .withArgs(policyId, fraudChecker.address, fraudReason);

      const policy = await cropInsurance.policies(policyId);
      expect(policy.status).to.equal(STATUS_UNDER_REVIEW);

      // Automated settlement must now revert
      await expect(cropInsurance.settlePolicy(policyId)).to.be.revertedWithCustomError(
        cropInsurance,
        "PolicyNotActive"
      );
    });

    it("should allow admin to escalate policy to UNDER_REVIEW after timeout grace period", async function () {
      await time.increaseTo(endTime + 1);
      // Only 1 oracle reported
      await cropInsurance.connect(oracleWeather).submitReport(policyId, SOURCE_WEATHER, TIER_1);

      // Attempt before grace period (14 days)
      await expect(
        cropInsurance.connect(admin).escalateTimeout(policyId)
      ).to.be.revertedWithCustomError(cropInsurance, "TimeoutNotReached");

      // Fast forward past grace period: 14 days + 1 second
      await time.increase(14 * 24 * 3600 + 1);

      await expect(cropInsurance.connect(admin).escalateTimeout(policyId))
        .to.emit(cropInsurance, "PolicyTimedOutToReview")
        .withArgs(policyId, admin.address);

      const policy = await cropInsurance.policies(policyId);
      expect(policy.status).to.equal(STATUS_UNDER_REVIEW);
    });
  });

  describe("6. Dispute Mechanism Flow", function () {
    let policyId: number;

    beforeEach(async function () {
      const premium = await cropInsurance.calculatePremium(SUM_INSURED, REGION_ANANTAPUR);
      const currentTime = await time.latest();
      const endTime = currentTime + 1000;

      await cropInsurance
        .connect(farmer1)
        .createPolicy(
          DUMMY_LAND_1,
          CROP_GROUNDNUT,
          REGION_ANANTAPUR,
          SUM_INSURED,
          currentTime + 10,
          endTime,
          DUMMY_RULES_HASH,
          { value: premium }
        );
      policyId = 1;

      await time.increaseTo(endTime + 1);

      // Oracles report Tier 1 (25% payout)
      await cropInsurance.connect(oracleWeather).submitReport(policyId, SOURCE_WEATHER, TIER_1);
      await cropInsurance.connect(oracleSatellite).submitReport(policyId, SOURCE_SATELLITE, TIER_1);
      await cropInsurance.settlePolicy(policyId);
    });

    it("should allow farmer to open dispute and reviewer to upgrade payout", async function () {
      // Farmer opens dispute within 7-day window
      await expect(cropInsurance.connect(farmer1).openDispute(policyId))
        .to.emit(cropInsurance, "DisputeOpened")
        .withArgs(policyId, farmer1.address);

      expect((await cropInsurance.disputes(policyId)).exists).to.be.true;

      // Reviewer upgrades from Tier 1 (0.25 ETH) to Tier 3 (1.0 ETH)
      const disputeReason = ethers.keccak256(
        ethers.toUtf8Bytes("OFFICIAL_REVENUE_BOARD_DESICCATION_RECORD")
      );
      const additionalPayout = ethers.parseEther("0.75"); // 1.0 - 0.25 = 0.75 ETH

      await expect(
        cropInsurance.connect(disputeReviewer).resolveDispute(policyId, TIER_3, disputeReason)
      )
        .to.emit(cropInsurance, "DisputeResolved")
        .withArgs(policyId, disputeReviewer.address, TIER_3, additionalPayout, disputeReason);

      const policy = await cropInsurance.policies(policyId);
      expect(policy.finalTier).to.equal(TIER_3);
      expect(policy.payoutAmount).to.equal(ethers.parseEther("1.0"));

      // Farmer should now have total claimable balance of 1.0 ETH
      expect(await cropInsurance.claimableBalance(farmer1.address)).to.equal(
        ethers.parseEther("1.0")
      );
    });

    it("should revert if dispute is opened after dispute window closes", async function () {
      // Fast forward past 7-day dispute window
      await time.increase(7 * 24 * 3600 + 1);

      await expect(
        cropInsurance.connect(farmer1).openDispute(policyId)
      ).to.be.revertedWithCustomError(cropInsurance, "DisputeWindowClosed");
    });

    it("should revert if a non-farmer opens dispute", async function () {
      await expect(
        cropInsurance.connect(unauthorized).openDispute(policyId)
      ).to.be.revertedWithCustomError(cropInsurance, "NotPolicyFarmer");
    });
  });

  describe("7. Pull Payout Withdrawal & Reentrancy Security", function () {
    it("should allow farmer to pull payout safely and prevent double withdrawals", async function () {
      const premium = await cropInsurance.calculatePremium(SUM_INSURED, REGION_ANANTAPUR);
      const currentTime = await time.latest();
      const endTime = currentTime + 1000;

      await cropInsurance
        .connect(farmer1)
        .createPolicy(
          DUMMY_LAND_1,
          CROP_GROUNDNUT,
          REGION_ANANTAPUR,
          SUM_INSURED,
          currentTime + 10,
          endTime,
          DUMMY_RULES_HASH,
          { value: premium }
        );
      await time.increaseTo(endTime + 1);

      await cropInsurance.connect(oracleWeather).submitReport(1, SOURCE_WEATHER, TIER_2);
      await cropInsurance.connect(oracleSatellite).submitReport(1, SOURCE_SATELLITE, TIER_2);
      await cropInsurance.settlePolicy(1);

      const payout = ethers.parseEther("0.5");
      expect(await cropInsurance.claimableBalance(farmer1.address)).to.equal(payout);

      // Farmer pulls payout
      await expect(() => cropInsurance.connect(farmer1).withdrawPayout()).to.changeEtherBalances(
        [cropInsurance, farmer1],
        [-payout, payout]
      );

      // Balance is now zero
      expect(await cropInsurance.claimableBalance(farmer1.address)).to.equal(0);

      // Attempting second withdrawal reverts
      await expect(cropInsurance.connect(farmer1).withdrawPayout()).to.be.revertedWithCustomError(
        cropInsurance,
        "NoClaimableFunds"
      );
    });

    it("should defeat reentrancy attack attempts via ReentrancyGuard and Checks-Effects-Interactions", async function () {
      // Deploy MaliciousAttacker contract
      const AttackerFactory = await ethers.getContractFactory("MaliciousAttacker");
      const attackerContract = await AttackerFactory.deploy(await cropInsurance.getAddress());
      await attackerContract.waitForDeployment();

      const attackerAddress = await attackerContract.getAddress();
      const premium = await cropInsurance.calculatePremium(SUM_INSURED, REGION_ANANTAPUR);
      const currentTime = await time.latest();
      const endTime = currentTime + 1000;

      // Attacker contract purchases a policy
      await attackerContract.buyPolicy(
        DUMMY_LAND_2,
        CROP_GROUNDNUT,
        REGION_ANANTAPUR,
        SUM_INSURED,
        currentTime + 10,
        endTime,
        DUMMY_RULES_HASH,
        { value: premium }
      );

      await time.increaseTo(endTime + 1);

      // Oracles report Tier 2 (0.5 ETH)
      await cropInsurance.connect(oracleWeather).submitReport(1, SOURCE_WEATHER, TIER_2);
      await cropInsurance.connect(oracleSatellite).submitReport(1, SOURCE_SATELLITE, TIER_2);
      await cropInsurance.settlePolicy(1);

      // Initial insurance pool balance before attack
      const poolBefore = await cropInsurance.riskPoolBalance();

      // Attacker executes attack() which calls withdrawPayout(), triggering receive() reentrancy
      await attackerContract.attack();

      // Attacker contract only receives its exact owed amount (0.5 ETH), cannot drain the pool
      expect(await ethers.provider.getBalance(attackerAddress)).to.equal(ethers.parseEther("0.5"));
      // The reentrant call was completely blocked
      expect(await attackerContract.reentrancySucceeded()).to.be.false;
      // Pool balance remains completely intact
      expect(await cropInsurance.riskPoolBalance()).to.equal(poolBefore);
    });
  });
});
