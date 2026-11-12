// SPDX-License-Identifier: MIT
/* solhint-disable */
pragma solidity ^0.8.20;

import {CropInsurance} from "../CropInsurance.sol";

/**
 * @title MaliciousAttacker
 * @notice Test helper contract attempting reentrant withdrawal against CropInsurance.
 * @dev Used specifically for testing that ReentrancyGuard and Checks-Effects-Interactions prevent reentrancy.
 */
contract MaliciousAttacker {
    CropInsurance public immutable insurance;
    uint256 public attackCount;

    constructor(address payable _insurance) {
        insurance = CropInsurance(_insurance);
    }

    function buyPolicy(
        bytes32 landHash,
        CropInsurance.CropCode crop,
        CropInsurance.Region region,
        uint256 sumInsured,
        uint256 startTime,
        uint256 endTime,
        bytes32 rulesHash
    ) external payable returns (uint256) {
        return
            insurance.createPolicy{value: msg.value}(
                landHash,
                crop,
                region,
                sumInsured,
                startTime,
                endTime,
                rulesHash
            );
    }

    function attack() external {
        attackCount++;
        insurance.withdrawPayout();
    }

    bool public reentrancySucceeded;

    receive() external payable {
        if (address(insurance).balance > 0 && attackCount < 3) {
            attackCount++;
            // Attempt reentrancy via low-level call
            (bool success, ) = address(insurance).call(abi.encodeWithSignature("withdrawPayout()"));
            if (success) {
                reentrancySucceeded = true;
            }
        }
    }
}
