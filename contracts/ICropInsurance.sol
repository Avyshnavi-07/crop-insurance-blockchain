// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title ICropInsurance
 * @notice Research prototype interface for hardware-free multi-source crop insurance.
 * @dev Full implementation built in Phase 1.
 */
interface ICropInsurance {
    /// @notice Severity tiers for payout calculation (assumptions documented in config/tier_rules.json)
    enum SeverityTier {
        TIER_0_NORMAL, // 0% payout
        TIER_1_MODERATE, // 25% payout
        TIER_2_SEVERE, // 50% payout
        TIER_3_CATASTROPHIC // 100% payout
    }

    /// @notice Lifecycle status of an individual insurance policy
    enum PolicyStatus {
        ACTIVE,
        SETTLED,
        UNDER_REVIEW,
        EXPIRED
    }
}
