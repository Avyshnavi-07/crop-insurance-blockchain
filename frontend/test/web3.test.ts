import { describe, expect, it } from 'vitest';
import { ethers } from 'ethers';
import {
  computeLandHash,
  computeRulesHashFromObject,
  decodeContractError,
  DEFAULT_RULES_HASH,
  getStatusBadge,
  getTierBadge,
  normalizePolygonCoordinates,
  validateCoordinates,
  CROP_INSURANCE_INTERFACE,
} from '../src/utils/web3';
import { PolicyStatus, SeverityTier } from '../src/types';

describe('Web3 Utility Suite', () => {
  describe('Boundary Normalization & Hashing', () => {
    it('normalizes vertex coordinates to 5 decimal places', () => {
      const input = '14.681234, 77.600001; 14.690000, 77.600000; 14.690000, 77.610000';
      const normalized = normalizePolygonCoordinates(input);
      expect(normalized).toBe('[14.68123,77.60000];[14.69000,77.60000];[14.69000,77.61000]');
    });

    it('rejects polygons with fewer than 3 vertices', () => {
      const input = '14.68, 77.60; 14.69, 77.60';
      expect(() => normalizePolygonCoordinates(input)).toThrow('at least 3 coordinate vertices');
    });

    it('rejects invalid or empty coordinate text', () => {
      expect(() => normalizePolygonCoordinates('')).toThrow('cannot be empty');
      expect(() => normalizePolygonCoordinates('abc,def;ghi,jkl;mno,pqr')).toThrow('Non-numeric');
    });

    it('computes deterministic keccak256 hash matching bytes32 shape', () => {
      const input = '14.68, 77.60; 14.69, 77.60; 14.69, 77.61; 14.68, 77.61';
      const hash1 = computeLandHash(input);
      const hash2 = computeLandHash(input);
      expect(hash1).toBe(hash2);
      expect(hash1).toMatch(/^0x[a-fA-F0-9]{64}$/);
    });

    it('validates Andhra Pradesh regional coordinates correctly', () => {
      // Valid Anantapur farm
      expect(validateCoordinates(14.68, 77.60).valid).toBe(true);
      // Valid Kurnool farm
      expect(validateCoordinates(15.82, 78.03).valid).toBe(true);
      // Outside AP (Delhi)
      const outOfBounds = validateCoordinates(28.61, 77.20);
      expect(outOfBounds.valid).toBe(false);
      expect(outOfBounds.error).toContain('outside Andhra Pradesh');
    });
  });

  describe('Rules Hash Verification', () => {
    it('matches Python compute_rules_hash() canonical value', () => {
      const hash = computeRulesHashFromObject();
      expect(hash).toBe(DEFAULT_RULES_HASH);
      expect(hash).toBe('0x4fdfda6724aab3b64412a7aae531b847661e173d150744ecfb63b2c5aa2c670c');
    });
  });

  describe('Contract Custom Error Decoding', () => {
    it('decodes InsufficientRiskPool error with formatted ETH amounts', () => {
      const available = ethers.parseEther('10.0');
      const required = ethers.parseEther('15.0');
      const encoded = CROP_INSURANCE_INTERFACE.encodeErrorResult('InsufficientRiskPool', [available, required]);

      const decoded = decodeContractError({ data: encoded });
      expect(decoded).toContain('Insufficient Risk Pool');
      expect(decoded).toContain('10.0 ETH');
      expect(decoded).toContain('15.0 ETH');
    });

    it('decodes LandAlreadyInsured error', () => {
      const dummyLand = ethers.keccak256(ethers.toUtf8Bytes('parcel123'));
      const encoded = CROP_INSURANCE_INTERFACE.encodeErrorResult('LandAlreadyInsured', [dummyLand]);

      const decoded = decodeContractError({ data: encoded });
      expect(decoded).toContain('Land Already Insured');
      expect(decoded).toContain('active policy');
    });

    it('decodes ConsensusNotReached error', () => {
      const encoded = CROP_INSURANCE_INTERFACE.encodeErrorResult('ConsensusNotReached', [1, 2]);

      const decoded = decodeContractError({ data: encoded });
      expect(decoded).toContain('Consensus Not Reached');
      expect(decoded).toContain('2 reports');
    });

    it('decodes DisputeWindowClosed error', () => {
      const encoded = CROP_INSURANCE_INTERFACE.encodeErrorResult('DisputeWindowClosed', [1000, 900]);

      const decoded = decodeContractError({ data: encoded });
      expect(decoded).toContain('Dispute Window Closed');
    });

    it('decodes AccessControlUnauthorizedAccount error', () => {
      const dummyAddr = '0x1111111111111111111111111111111111111111';
      const dummyRole = ethers.keccak256(ethers.toUtf8Bytes('ORACLE_WEATHER_ROLE'));
      const encoded = CROP_INSURANCE_INTERFACE.encodeErrorResult('AccessControlUnauthorizedAccount', [
        dummyAddr,
        dummyRole,
      ]);

      const decoded = decodeContractError({ data: encoded });
      expect(decoded).toContain('Access Denied');
      expect(decoded).toContain(dummyAddr);
    });

    it('handles generic non-contract errors gracefully', () => {
      expect(decodeContractError({ message: 'user rejected transaction' })).toContain('rejected by user');
      expect(decodeContractError({ message: 'insufficient funds for gas' })).toContain('Insufficient wallet ETH');
      expect(decodeContractError(new Error('Network timeout'))).toBe('Network timeout');
      expect(decodeContractError('Custom string error')).toBe('Custom string error');
    });
  });

  describe('Enum & Badge Mappings', () => {
    it('returns correct status badges for all policy statuses', () => {
      expect(getStatusBadge(PolicyStatus.ACTIVE).label).toBe('ACTIVE');
      expect(getStatusBadge(PolicyStatus.AWAITING_ORACLES).label).toBe('AWAITING ORACLES');
      expect(getStatusBadge(PolicyStatus.SETTLED).label).toBe('SETTLED');
      expect(getStatusBadge(PolicyStatus.UNDER_REVIEW).label).toBe('UNDER REVIEW');
      expect(getStatusBadge(PolicyStatus.DISPUTED).label).toBe('DISPUTED');
      expect(getStatusBadge(PolicyStatus.CLOSED).label).toBe('CLOSED');
    });

    it('returns correct tier badges and payout percentages', () => {
      expect(getTierBadge(SeverityTier.NONE).payoutPct).toBe(0);
      expect(getTierBadge(SeverityTier.MODERATE).payoutPct).toBe(25);
      expect(getTierBadge(SeverityTier.SEVERE).payoutPct).toBe(50);
      expect(getTierBadge(SeverityTier.CATASTROPHIC).payoutPct).toBe(100);
    });
  });
});
