// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/**
 * @title CropInsurance
 * @notice Hardware-free blockchain crop-insurance research prototype.
 * @dev Implements 2-of-3 oracle consensus, median fallback, tiered settlements,
 *      checks-effects-interactions, pull payouts, fraud hooks, and dispute resolution.
 *      Designed for groundnut farming in Andhra Pradesh (Anantapur, Kurnool, Kadapa).
 */
contract CropInsurance is AccessControl, ReentrancyGuard {
    // =========================================================================
    // Roles Definition
    // =========================================================================
    bytes32 public constant ORACLE_WEATHER_ROLE = keccak256("ORACLE_WEATHER_ROLE");
    bytes32 public constant ORACLE_SATELLITE_ROLE = keccak256("ORACLE_SATELLITE_ROLE");
    bytes32 public constant ORACLE_SOIL_ROLE = keccak256("ORACLE_SOIL_ROLE");
    bytes32 public constant FRAUD_CHECKER_ROLE = keccak256("FRAUD_CHECKER_ROLE");
    bytes32 public constant DISPUTE_REVIEWER_ROLE = keccak256("DISPUTE_REVIEWER_ROLE");

    // =========================================================================
    // Enums & Types
    // =========================================================================
    enum SeverityTier {
        TIER_0_NORMAL, // 0% payout
        TIER_1_MODERATE, // 25% payout
        TIER_2_SEVERE, // 50% payout
        TIER_3_CATASTROPHIC // 100% payout
    }

    enum PolicyStatus {
        ACTIVE,
        SETTLED,
        UNDER_REVIEW,
        EXPIRED
    }

    enum OracleSource {
        WEATHER, // Open-Meteo rainfall deficit
        SATELLITE, // Sentinel-2 NDVI canopy deficit
        SOIL // NASA SMAP root-zone moisture deficit
    }

    enum CropCode {
        GROUNDNUT,
        CHICKPEA,
        COTTON,
        RICE
    }

    enum Region {
        ANANTAPUR,
        KURNOOL,
        KADAPA
    }

    // =========================================================================
    // Structs
    // =========================================================================
    struct OracleReport {
        bool submitted;
        SeverityTier tier;
        uint256 timestamp;
    }

    struct Policy {
        uint256 id;
        address payable farmer;
        bytes32 landHash;
        CropCode crop;
        Region region;
        uint256 sumInsured;
        uint256 premium;
        uint256 startTime;
        uint256 endTime;
        PolicyStatus status;
        bytes32 rulesHash;
        SeverityTier finalTier;
        uint256 payoutAmount;
        uint256 settledAt;
    }

    struct Dispute {
        bool exists;
        bool resolved;
        SeverityTier originalTier;
        SeverityTier resolvedTier;
        bytes32 reasonHash;
        uint256 openedAt;
        uint256 resolvedAt;
    }

    // =========================================================================
    // State Variables & Constants
    // =========================================================================
    uint256 public constant BPS_DENOMINATOR = 10000;
    uint256 public constant BASE_PREMIUM_BPS = 300; // 3.00% base rate
    uint256 public constant TIMEOUT_GRACE_PERIOD = 14 days;
    uint256 public constant DISPUTE_WINDOW = 7 days;

    uint256 public nextPolicyId = 1;
    uint256 public riskPoolBalance;
    uint256 public reservedExposure;

    mapping(Region => uint256) public regionalRiskBps;
    mapping(bytes32 => bool) public activeLandHashes;
    mapping(uint256 => Policy) public policies;
    mapping(uint256 => mapping(OracleSource => OracleReport)) public oracleReports;
    mapping(uint256 => Dispute) public disputes;
    mapping(address => uint256) public claimableBalance;

    // =========================================================================
    // Custom Errors
    // =========================================================================
    error InsufficientRiskPool(uint256 available, uint256 required);
    error LandAlreadyInsured(bytes32 landHash);
    error InvalidPolicyDuration(uint256 start, uint256 end);
    error IncorrectPremiumPaid(uint256 expected, uint256 actual);
    error PolicyNotActive(uint256 policyId, PolicyStatus currentStatus);
    error SeasonNotEnded(uint256 currentTime, uint256 seasonEndTime);
    error OracleAlreadyReported(uint256 policyId, OracleSource source);
    error UnauthorizedOracleSource(address caller, OracleSource source);
    error ConsensusNotReached(uint256 policyId, uint8 reportCount);
    error TimeoutNotReached(uint256 currentTime, uint256 timeoutTimestamp);
    error DisputeWindowClosed(uint256 currentTime, uint256 deadline);
    error DisputeAlreadyExists(uint256 policyId);
    error DisputeNotFound(uint256 policyId);
    error DisputeAlreadyResolved(uint256 policyId);
    error NotPolicyFarmer(uint256 policyId, address caller);
    error PolicyNotSettled(uint256 policyId);
    error NoClaimableFunds();
    error TransferFailed();
    error ZeroAddress();
    error ZeroAmount();

    // =========================================================================
    // Events
    // =========================================================================
    event RiskPoolFunded(address indexed donor, uint256 amount);
    event RiskPoolWithdrawn(address indexed admin, uint256 amount);
    event RegionalRiskUpdated(Region indexed region, uint256 riskBps);
    event PolicyCreated(
        uint256 indexed policyId,
        address indexed farmer,
        bytes32 indexed landHash,
        Region region,
        CropCode crop,
        uint256 sumInsured,
        uint256 premium,
        uint256 startTime,
        uint256 endTime,
        bytes32 rulesHash
    );
    event OracleReportSubmitted(
        uint256 indexed policyId,
        OracleSource indexed source,
        address indexed oracle,
        SeverityTier tier
    );
    event PolicySettled(
        uint256 indexed policyId,
        SeverityTier consensusTier,
        uint256 payoutAmount,
        PolicyStatus newStatus
    );
    event PolicyFlaggedFraud(uint256 indexed policyId, address indexed checker, bytes32 reasonHash);
    event PolicyTimedOutToReview(uint256 indexed policyId, address indexed admin);
    event DisputeOpened(uint256 indexed policyId, address indexed farmer);
    event DisputeResolved(
        uint256 indexed policyId,
        address indexed reviewer,
        SeverityTier overrideTier,
        uint256 additionalPayout,
        bytes32 reasonHash
    );
    event PayoutWithdrawn(address indexed farmer, uint256 amount);

    // =========================================================================
    // Constructor & Initialization
    // =========================================================================
    /**
     * @notice Initializes contract and sets up role-based access control and default regional risk rates.
     * @param admin Address receiving DEFAULT_ADMIN_ROLE
     */
    constructor(address admin) {
        if (admin == address(0)) revert ZeroAddress();

        _grantRole(DEFAULT_ADMIN_ROLE, admin);

        // Default regional risk rates (assumptions documented in config/tier_rules.json)
        regionalRiskBps[Region.ANANTAPUR] = 350; // 3.50%
        regionalRiskBps[Region.KURNOOL] = 250; // 2.50%
        regionalRiskBps[Region.KADAPA] = 200; // 2.00%
    }

    // =========================================================================
    // Risk Pool Management
    // =========================================================================
    /**
     * @notice Allows underwriters or government sponsors to inject capital into the risk pool.
     */
    function fundRiskPool() external payable {
        if (msg.value == 0) revert ZeroAmount();
        riskPoolBalance += msg.value;
        emit RiskPoolFunded(msg.sender, msg.value);
    }

    /**
     * @notice Allows admin to withdraw unreserved funds from the risk pool.
     * @param amount Amount in wei to withdraw
     */
    function withdrawRiskPool(uint256 amount) external onlyRole(DEFAULT_ADMIN_ROLE) nonReentrant {
        if (amount == 0) revert ZeroAmount();
        if (riskPoolBalance < reservedExposure + amount) {
            revert InsufficientRiskPool(riskPoolBalance - reservedExposure, amount);
        }

        riskPoolBalance -= amount;
        emit RiskPoolWithdrawn(msg.sender, amount);

        (bool success, ) = msg.sender.call{value: amount}("");
        if (!success) revert TransferFailed();
    }

    /**
     * @notice Allows admin to update regional risk rate in basis points.
     * @param region Target district/region
     * @param riskBps Regional risk addition in basis points (1% = 100 bps)
     */
    function setRegionalRiskBps(
        Region region,
        uint256 riskBps
    ) external onlyRole(DEFAULT_ADMIN_ROLE) {
        regionalRiskBps[region] = riskBps;
        emit RegionalRiskUpdated(region, riskBps);
    }

    // =========================================================================
    // Policy Creation & Underwriting
    // =========================================================================
    /**
     * @notice Calculates required premium for given sum insured and region.
     * @param sumInsured The total coverage value in wei
     * @param region Regional risk classification
     * @return Required premium amount in wei
     */
    function calculatePremium(uint256 sumInsured, Region region) public view returns (uint256) {
        uint256 totalRateBps = BASE_PREMIUM_BPS + regionalRiskBps[region];
        return (sumInsured * totalRateBps) / BPS_DENOMINATOR;
    }

    /**
     * @notice Purchases a crop insurance policy for a verifiable parcel of land.
     * @dev Checks solvency: risk pool must cover existing reserved exposure + new sum insured.
     * @param landHash Keccak256 hash of land cadastral boundary/polygon
     * @param crop Crop classification enum
     * @param region Geographic district
     * @param sumInsured Sum insured value in wei
     * @param startTime Season start timestamp
     * @param endTime Season end timestamp
     * @param rulesHash Keccak256 hash of tier_rules.json committing thresholds on-chain
     * @return policyId Newly minted policy identifier
     */
    function createPolicy(
        bytes32 landHash,
        CropCode crop,
        Region region,
        uint256 sumInsured,
        uint256 startTime,
        uint256 endTime,
        bytes32 rulesHash
    ) external payable nonReentrant returns (uint256 policyId) {
        if (sumInsured == 0) revert ZeroAmount();
        if (startTime >= endTime) revert InvalidPolicyDuration(startTime, endTime);
        if (activeLandHashes[landHash]) revert LandAlreadyInsured(landHash);

        uint256 requiredPremium = calculatePremium(sumInsured, region);
        if (msg.value != requiredPremium) {
            revert IncorrectPremiumPaid(requiredPremium, msg.value);
        }

        // Solvency verification: pool balance + new premium must cover total reserved exposure
        uint256 newTotalPool = riskPoolBalance + msg.value;
        uint256 newTotalExposure = reservedExposure + sumInsured;
        if (newTotalPool < newTotalExposure) {
            revert InsufficientRiskPool(newTotalPool, newTotalExposure);
        }

        // Commit state (Checks-Effects)
        policyId = nextPolicyId++;
        activeLandHashes[landHash] = true;
        riskPoolBalance = newTotalPool;
        reservedExposure = newTotalExposure;

        policies[policyId] = Policy({
            id: policyId,
            farmer: payable(msg.sender),
            landHash: landHash,
            crop: crop,
            region: region,
            sumInsured: sumInsured,
            premium: msg.value,
            startTime: startTime,
            endTime: endTime,
            status: PolicyStatus.ACTIVE,
            rulesHash: rulesHash,
            finalTier: SeverityTier.TIER_0_NORMAL,
            payoutAmount: 0,
            settledAt: 0
        });

        emit PolicyCreated(
            policyId,
            msg.sender,
            landHash,
            region,
            crop,
            sumInsured,
            msg.value,
            startTime,
            endTime,
            rulesHash
        );
    }

    // =========================================================================
    // Oracle Report Submission
    // =========================================================================
    /**
     * @notice Submits a severity tier report from an authorized source oracle.
     * @dev Report can only be submitted after season end and only once per oracle source.
     * @param policyId Target policy
     * @param source Oracle source identifier (WEATHER, SATELLITE, SOIL)
     * @param tier Reported severity tier (0 to 3)
     */
    function submitReport(uint256 policyId, OracleSource source, SeverityTier tier) external {
        Policy storage policy = policies[policyId];
        if (policy.status != PolicyStatus.ACTIVE) {
            revert PolicyNotActive(policyId, policy.status);
        }
        if (block.timestamp < policy.endTime) {
            revert SeasonNotEnded(block.timestamp, policy.endTime);
        }

        _validateOracleRole(source, msg.sender);

        OracleReport storage report = oracleReports[policyId][source];
        if (report.submitted) {
            revert OracleAlreadyReported(policyId, source);
        }

        report.submitted = true;
        report.tier = tier;
        report.timestamp = block.timestamp;

        emit OracleReportSubmitted(policyId, source, msg.sender, tier);
    }

    /**
     * @dev Internal helper validating caller possesses corresponding role for source.
     */
    function _validateOracleRole(OracleSource source, address caller) internal view {
        if (source == OracleSource.WEATHER) {
            if (!hasRole(ORACLE_WEATHER_ROLE, caller))
                revert UnauthorizedOracleSource(caller, source);
        } else if (source == OracleSource.SATELLITE) {
            if (!hasRole(ORACLE_SATELLITE_ROLE, caller))
                revert UnauthorizedOracleSource(caller, source);
        } else if (source == OracleSource.SOIL) {
            if (!hasRole(ORACLE_SOIL_ROLE, caller)) revert UnauthorizedOracleSource(caller, source);
        }
    }

    // =========================================================================
    // Consensus & Settlement Logic
    // =========================================================================
    /**
     * @notice Evaluates oracle consensus and settles policy if consensus conditions are met.
     * @dev Consensus rule:
     *      - Any 2 matching reports win.
     *      - If 3 reports exist and all differ, median tier is selected.
     *      - If only 2 reports exist and they differ, settlement waits for 3rd report.
     * @param policyId Target policy to settle
     */
    function settlePolicy(uint256 policyId) external nonReentrant {
        Policy storage policy = policies[policyId];
        if (policy.status != PolicyStatus.ACTIVE) {
            revert PolicyNotActive(policyId, policy.status);
        }

        (bool hasConsensus, SeverityTier winningTier) = evaluateConsensus(policyId);
        if (!hasConsensus) {
            (uint8 count, , ) = getOracleReportsSummary(policyId);
            revert ConsensusNotReached(policyId, count);
        }

        // Checks-Effects: Free land hash and release reserved exposure
        activeLandHashes[policy.landHash] = false;
        reservedExposure -= policy.sumInsured;

        uint256 payout = calculatePayout(policy.sumInsured, winningTier);

        policy.status = PolicyStatus.SETTLED;
        policy.finalTier = winningTier;
        policy.payoutAmount = payout;
        policy.settledAt = block.timestamp;

        // Deduct payout from risk pool and credit farmer's pull-balance
        if (payout > 0) {
            riskPoolBalance -= payout;
            claimableBalance[policy.farmer] += payout;
        }

        emit PolicySettled(policyId, winningTier, payout, PolicyStatus.SETTLED);
    }

    /**
     * @notice Evaluates consensus across submitted oracle reports.
     * @param policyId Target policy
     * @return hasConsensus True if 2-of-3 agree or all 3 submitted (median chosen)
     * @return winningTier Winning severity tier
     */
    function evaluateConsensus(
        uint256 policyId
    ) public view returns (bool hasConsensus, SeverityTier winningTier) {
        (uint8 count, OracleReport[3] memory reports, ) = getOracleReportsSummary(policyId);

        if (count < 2) {
            return (false, SeverityTier.TIER_0_NORMAL);
        }

        if (count == 2) {
            // Find which two were submitted
            SeverityTier tierA = SeverityTier.TIER_0_NORMAL;
            SeverityTier tierB = SeverityTier.TIER_0_NORMAL;
            bool foundFirst = false;

            for (uint256 i = 0; i < 3; i++) {
                if (reports[i].submitted) {
                    if (!foundFirst) {
                        tierA = reports[i].tier;
                        foundFirst = true;
                    } else {
                        tierB = reports[i].tier;
                    }
                }
            }

            if (tierA == tierB) {
                return (true, tierA);
            }
            return (false, SeverityTier.TIER_0_NORMAL); // Disagreement: wait for 3rd report
        }

        // All 3 reports submitted
        SeverityTier tW = reports[0].tier;
        SeverityTier tSat = reports[1].tier;
        SeverityTier tSoil = reports[2].tier;

        // Check pairs
        if (tW == tSat || tW == tSoil) {
            return (true, tW);
        }
        if (tSat == tSoil) {
            return (true, tSat);
        }

        // All 3 differ: select median
        winningTier = _calculateMedian(tW, tSat, tSoil);
        return (true, winningTier);
    }

    /**
     * @dev Computes median of 3 distinct severity tiers.
     */
    function _calculateMedian(
        SeverityTier a,
        SeverityTier b,
        SeverityTier c
    ) internal pure returns (SeverityTier) {
        uint8 valA = uint8(a);
        uint8 valB = uint8(b);
        uint8 valC = uint8(c);

        if ((valA > valB) != (valA > valC)) {
            return a;
        } else if ((valB > valA) != (valB > valC)) {
            return b;
        } else {
            return c;
        }
    }

    /**
     * @notice Helper returning submitted reports and total count for a policy.
     * @param policyId Target policy
     */
    function getOracleReportsSummary(
        uint256 policyId
    )
        public
        view
        returns (uint8 count, OracleReport[3] memory reports, OracleSource[3] memory sources)
    {
        sources[0] = OracleSource.WEATHER;
        sources[1] = OracleSource.SATELLITE;
        sources[2] = OracleSource.SOIL;

        reports[0] = oracleReports[policyId][OracleSource.WEATHER];
        reports[1] = oracleReports[policyId][OracleSource.SATELLITE];
        reports[2] = oracleReports[policyId][OracleSource.SOIL];

        for (uint256 i = 0; i < 3; i++) {
            if (reports[i].submitted) {
                count++;
            }
        }
    }

    /**
     * @notice Calculates tiered payout based on sum insured and consensus severity tier.
     * @param sumInsured Total sum insured in wei
     * @param tier Severity tier (0: 0%, 1: 25%, 2: 50%, 3: 100%)
     */
    function calculatePayout(uint256 sumInsured, SeverityTier tier) public pure returns (uint256) {
        if (tier == SeverityTier.TIER_0_NORMAL) {
            return 0;
        } else if (tier == SeverityTier.TIER_1_MODERATE) {
            return (sumInsured * 25) / 100;
        } else if (tier == SeverityTier.TIER_2_SEVERE) {
            return (sumInsured * 50) / 100;
        } else {
            return sumInsured;
        }
    }

    // =========================================================================
    // Fraud Detection Hook & Timeout Escalation
    // =========================================================================
    /**
     * @notice Allows trusted fraud checker to flag suspicious policies before payout,
     *         pausing automated settlement and moving policy to UNDER_REVIEW.
     * @param policyId Target policy
     * @param reasonHash Keccak256 hash describing the fraud indicator (e.g. duplicate land, synthetic anomaly)
     */
    function flagFraud(uint256 policyId, bytes32 reasonHash) external onlyRole(FRAUD_CHECKER_ROLE) {
        Policy storage policy = policies[policyId];
        if (policy.status != PolicyStatus.ACTIVE) {
            revert PolicyNotActive(policyId, policy.status);
        }

        policy.status = PolicyStatus.UNDER_REVIEW;
        emit PolicyFlaggedFraud(policyId, msg.sender, reasonHash);
    }

    /**
     * @notice If season has ended and consensus has not been reached after grace period,
     *         allows admin to move policy to UNDER_REVIEW for manual inquiry.
     * @param policyId Target policy
     */
    function escalateTimeout(uint256 policyId) external onlyRole(DEFAULT_ADMIN_ROLE) {
        Policy storage policy = policies[policyId];
        if (policy.status != PolicyStatus.ACTIVE) {
            revert PolicyNotActive(policyId, policy.status);
        }

        uint256 timeoutTimestamp = policy.endTime + TIMEOUT_GRACE_PERIOD;
        if (block.timestamp < timeoutTimestamp) {
            revert TimeoutNotReached(block.timestamp, timeoutTimestamp);
        }

        policy.status = PolicyStatus.UNDER_REVIEW;
        emit PolicyTimedOutToReview(policyId, msg.sender);
    }

    // =========================================================================
    // Dispute Mechanism
    // =========================================================================
    /**
     * @notice Allows a farmer to open a formal dispute within DISPUTE_WINDOW of settlement.
     * @param policyId Target settled policy
     */
    function openDispute(uint256 policyId) external {
        Policy storage policy = policies[policyId];
        if (policy.status != PolicyStatus.SETTLED) {
            revert PolicyNotSettled(policyId);
        }
        if (msg.sender != policy.farmer) {
            revert NotPolicyFarmer(policyId, msg.sender);
        }
        if (block.timestamp > policy.settledAt + DISPUTE_WINDOW) {
            revert DisputeWindowClosed(block.timestamp, policy.settledAt + DISPUTE_WINDOW);
        }
        if (disputes[policyId].exists) {
            revert DisputeAlreadyExists(policyId);
        }

        disputes[policyId] = Dispute({
            exists: true,
            resolved: false,
            originalTier: policy.finalTier,
            resolvedTier: policy.finalTier,
            reasonHash: bytes32(0),
            openedAt: block.timestamp,
            resolvedAt: 0
        });

        emit DisputeOpened(policyId, msg.sender);
    }

    /**
     * @notice Allows reviewer role to resolve dispute, adjusting tier and disbursing additional payout if appropriate.
     * @param policyId Target policy
     * @param overrideTier New final severity tier determined by manual review
     * @param reasonHash Off-chain documentation reference justifying dispute resolution
     */
    function resolveDispute(
        uint256 policyId,
        SeverityTier overrideTier,
        bytes32 reasonHash
    ) external onlyRole(DISPUTE_REVIEWER_ROLE) nonReentrant {
        Dispute storage dispute = disputes[policyId];
        if (!dispute.exists) revert DisputeNotFound(policyId);
        if (dispute.resolved) revert DisputeAlreadyResolved(policyId);

        Policy storage policy = policies[policyId];
        uint256 originalPayout = policy.payoutAmount;
        uint256 updatedPayout = calculatePayout(policy.sumInsured, overrideTier);
        uint256 additionalPayout = 0;

        if (updatedPayout > originalPayout) {
            additionalPayout = updatedPayout - originalPayout;
            if (riskPoolBalance < additionalPayout) {
                revert InsufficientRiskPool(riskPoolBalance, additionalPayout);
            }
            riskPoolBalance -= additionalPayout;
            claimableBalance[policy.farmer] += additionalPayout;
        }

        policy.finalTier = overrideTier;
        policy.payoutAmount = updatedPayout;

        dispute.resolved = true;
        dispute.resolvedTier = overrideTier;
        dispute.reasonHash = reasonHash;
        dispute.resolvedAt = block.timestamp;

        emit DisputeResolved(policyId, msg.sender, overrideTier, additionalPayout, reasonHash);
    }

    // =========================================================================
    // Pull Payout Withdrawal
    // =========================================================================
    /**
     * @notice Pull pattern: allows farmers to withdraw accrued payout balances.
     * @dev Implements checks-effects-interactions and ReentrancyGuard.
     */
    function withdrawPayout() external nonReentrant {
        uint256 amount = claimableBalance[msg.sender];
        if (amount == 0) revert NoClaimableFunds();

        // Effect before Interaction
        claimableBalance[msg.sender] = 0;

        emit PayoutWithdrawn(msg.sender, amount);

        // Interaction
        (bool success, ) = msg.sender.call{value: amount}("");
        if (!success) revert TransferFailed();
    }
}
