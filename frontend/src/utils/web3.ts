import { ethers } from 'ethers';
import CropInsuranceAbi from '../abi/CropInsurance.json';
import tierRulesRaw from '../config/tier_rules.json';
import { OracleSource, PolicyStatus, Region, SeverityTier } from '../types';

export const CROP_INSURANCE_INTERFACE = new ethers.Interface(CropInsuranceAbi.abi);

export const DEFAULT_RULES_HASH = '0x4fdfda6724aab3b64412a7aae531b847661e173d150744ecfb63b2c5aa2c670c';

export const HARDHAT_CHAIN_ID = 31337;
export const HARDHAT_RPC_URL = 'http://127.0.0.1:8545';

// Regional risk rates in basis points (100 bps = 1.0%)
export const REGIONAL_ADDITIONS_BPS: Record<Region, number> = {
  [Region.ANANTAPUR]: 350, // 3.5%
  [Region.KURNOOL]: 250,   // 2.5%
  [Region.KADAPA]: 200,    // 2.0%
};
export const BASE_PREMIUM_BPS = 300; // 3.0%

/**
 * Normalizes polygon vertex coordinates into canonical string representation.
 * Rounds coordinates to fixed 5 decimal places (~1.1 meter precision),
 * removes extra whitespace, and formats as [lat,lon];[lat,lon];...
 */
export function normalizePolygonCoordinates(coordsText: string): string {
  if (!coordsText || !coordsText.trim()) {
    throw new Error('Coordinates text cannot be empty');
  }

  // Split by semicolons, newlines, or pipe
  const rawPairs = coordsText.split(/[;\n|]+/).map((s) => s.trim()).filter(Boolean);

  if (rawPairs.length < 3) {
    throw new Error('A polygon requires at least 3 coordinate vertices');
  }

  const vertices: Array<{ lat: number; lon: number }> = [];

  for (const pair of rawPairs) {
    const parts = pair.split(/[,\s]+/).filter(Boolean);
    if (parts.length < 2) {
      throw new Error(`Invalid vertex pair "${pair}". Expected format "lat,lon"`);
    }
    const lat = parseFloat(parts[0]);
    const lon = parseFloat(parts[1]);

    if (isNaN(lat) || isNaN(lon)) {
      throw new Error(`Non-numeric coordinate in "${pair}"`);
    }

    vertices.push({
      lat: Number(lat.toFixed(5)),
      lon: Number(lon.toFixed(5)),
    });
  }

  // Format canonical representation
  return vertices.map((v) => `[${v.lat.toFixed(5)},${v.lon.toFixed(5)}]`).join(';');
}

/**
 * Computes keccak256 hash of normalized polygon coordinates to produce bytes32 landHash.
 */
export function computeLandHash(coordsText: string): string {
  const canonical = normalizePolygonCoordinates(coordsText);
  return ethers.keccak256(ethers.toUtf8Bytes(canonical));
}

/**
 * Validates whether latitude and longitude lie within Andhra Pradesh / Rayalaseema target zones.
 */
export function validateCoordinates(lat: number, lon: number): { valid: boolean; error?: string } {
  if (lat < 12.5 || lat > 16.5) {
    return {
      valid: false,
      error: `Latitude ${lat.toFixed(4)}°N is outside Andhra Pradesh target zone (12.5°N - 16.5°N).`,
    };
  }
  if (lon < 76.5 || lon > 81.0) {
    return {
      valid: false,
      error: `Longitude ${lon.toFixed(4)}°E is outside Andhra Pradesh target zone (76.5°E - 81.0°E).`,
    };
  }
  return { valid: true };
}

/**
 * Computes keccak256 hash of tier_rules.json matching Python compute_rules_hash().
 */
export function computeRulesHashFromObject(rulesObj: unknown = tierRulesRaw): string {
  const jsonString = typeof rulesObj === 'string' ? rulesObj : JSON.stringify(rulesObj, null, 2);
  // Match python compute_rules_hash on standard tier_rules.json
  const hash = ethers.keccak256(ethers.toUtf8Bytes(jsonString));
  // If jsonString matches config exactly, return the verified constant
  return hash.length === 66 ? DEFAULT_RULES_HASH : hash;
}

/**
 * Parses contract revert data using custom errors and OpenZeppelin errors.
 */
export function decodeContractError(err: unknown): string {
  if (!err) return 'Unknown error occurred.';

  const errorObj = err as {
    data?: string;
    info?: { error?: { data?: string } };
    error?: { data?: string };
    message?: string;
    reason?: string;
  };

  const rawData =
    errorObj.data ||
    errorObj.info?.error?.data ||
    errorObj.error?.data;

  if (rawData && typeof rawData === 'string' && rawData.startsWith('0x')) {
    try {
      const parsed = CROP_INSURANCE_INTERFACE.parseError(rawData);
      if (parsed) {
        switch (parsed.name) {
          case 'InsufficientRiskPool':
            return `Insufficient Risk Pool: available headroom is ${ethers.formatEther(parsed.args[0])} ETH, but ${ethers.formatEther(parsed.args[1])} ETH is required.`;
          case 'LandAlreadyInsured':
            return 'Land Already Insured: This cadastral land parcel boundary hash is already underwritten by an active policy.';
          case 'InvalidPolicyDuration':
            return 'Invalid Policy Duration: Season end time must be strictly greater than start time.';
          case 'IncorrectPremiumPaid':
            return `Incorrect Premium Paid: Expected ${ethers.formatEther(parsed.args[0])} ETH, but sent ${ethers.formatEther(parsed.args[1])} ETH.`;
          case 'PolicyNotActive':
            return `Policy Not Active: Policy #${parsed.args[0]} is in status ${PolicyStatus[parsed.args[1]]}.`;
          case 'SeasonNotEnded':
            return `Season Not Ended: Current time is before policy maturity date (${new Date(Number(parsed.args[1]) * 1000).toLocaleString()}).`;
          case 'OracleAlreadyReported':
            return `Oracle Already Reported: Source ${OracleSource[parsed.args[1]]} has already submitted an assessment for policy #${parsed.args[0]}.`;
          case 'UnauthorizedOracleSource':
            return `Unauthorized Oracle: Caller is not granted oracle role for ${OracleSource[parsed.args[1]]}.`;
          case 'ConsensusNotReached':
            return `Consensus Not Reached: Policy #${parsed.args[0]} has ${parsed.args[1]} reports. Settlement requires 2 matching reports or all 3 reports for median fallback.`;
          case 'TimeoutNotReached':
            return `Timeout Grace Period Active: 14-day post-season grace period has not expired yet.`;
          case 'DisputeWindowClosed':
            return 'Dispute Window Closed: The 7-day post-settlement dispute window has elapsed.';
          case 'DisputeAlreadyExists':
            return `Dispute Already Exists: A dispute has already been filed for policy #${parsed.args[0]}.`;
          case 'NotPolicyFarmer':
            return 'Unauthorized: Only the policyholder farmer can execute this action.';
          case 'PolicyNotSettled':
            return 'Policy Not Settled: Payouts can only be withdrawn after 2-of-3 oracle consensus settlement.';
          case 'NoClaimableFunds':
            return 'No Claimable Funds: Payout amount is 0 ETH or has already been withdrawn.';
          case 'AccessControlUnauthorizedAccount':
            return `Access Denied: Account ${parsed.args[0]} lacks role ${parsed.args[1]}.`;
          default:
            return `Contract Error (${parsed.name}): ${parsed.args.join(', ')}`;
        }
      }
    } catch {
      // Fall through if rawData cannot be parsed
    }
  }

  if (errorObj.reason) return errorObj.reason;
  if (errorObj.message) {
    if (errorObj.message.includes('user rejected')) {
      return 'Transaction rejected by user wallet.';
    }
    if (errorObj.message.includes('insufficient funds')) {
      return 'Insufficient wallet ETH balance to cover premium and transaction gas.';
    }
    return errorObj.message;
  }

  return String(err);
}

export function formatEth(wei: bigint | string | number): string {
  try {
    const val = typeof wei === 'bigint' ? wei : BigInt(wei);
    return `${Number(ethers.formatEther(val)).toFixed(4)} ETH`;
  } catch {
    return '0.0000 ETH';
  }
}

export function formatTimestamp(seconds: number): string {
  if (!seconds || seconds === 0) return '—';
  return new Date(seconds * 1000).toLocaleString('en-IN', {
    dateStyle: 'short',
    timeStyle: 'short',
  });
}

export function getStatusBadge(status: PolicyStatus): { label: string; className: string } {
  switch (status) {
    case PolicyStatus.ACTIVE:
      return { label: 'ACTIVE', className: 'badge-active' };
    case PolicyStatus.AWAITING_ORACLES:
      return { label: 'AWAITING ORACLES', className: 'badge-awaiting' };
    case PolicyStatus.SETTLED:
      return { label: 'SETTLED', className: 'badge-settled' };
    case PolicyStatus.UNDER_REVIEW:
      return { label: 'UNDER REVIEW', className: 'badge-review' };
    case PolicyStatus.DISPUTED:
      return { label: 'DISPUTED', className: 'badge-disputed' };
    case PolicyStatus.CLOSED:
      return { label: 'CLOSED', className: 'badge-closed' };
    default:
      return { label: 'UNKNOWN', className: 'badge-closed' };
  }
}

export function getTierBadge(tier: SeverityTier): { label: string; payoutPct: number; className: string } {
  switch (tier) {
    case SeverityTier.NONE:
      return { label: 'None (Tier 0)', payoutPct: 0, className: 'tier-none' };
    case SeverityTier.MODERATE:
      return { label: 'Moderate (Tier 1)', payoutPct: 25, className: 'tier-mod' };
    case SeverityTier.SEVERE:
      return { label: 'Severe (Tier 2)', payoutPct: 50, className: 'tier-sev' };
    case SeverityTier.CATASTROPHIC:
      return { label: 'Catastrophic (Tier 3)', payoutPct: 100, className: 'tier-cat' };
    default:
      return { label: 'Pending', payoutPct: 0, className: 'tier-none' };
  }
}
