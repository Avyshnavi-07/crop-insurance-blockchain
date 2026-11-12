import { expect } from "chai";
import { ethers } from "hardhat";

describe("Phase 0 Environment Verification", function () {
  it("should initialize Hardhat runtime and retrieve test signers", async function () {
    const signers = await ethers.getSigners();
    expect(signers.length).to.be.greaterThan(0);
    expect(signers[0].address).to.match(/^0x[a-fA-F0-9]{40}$/);
  });

  it("should verify basic assertion library and TypeScript configuration", function () {
    const a = 10;
    const b = 25;
    expect(a + b).to.equal(35);
  });
});
