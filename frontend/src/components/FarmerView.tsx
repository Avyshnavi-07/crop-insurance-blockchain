import React, { useEffect, useState } from 'react';
import { ethers } from 'ethers';
import {
  computeLandHash,
  DEFAULT_RULES_HASH,
  formatEth,
  formatTimestamp,
  getStatusBadge,
  getTierBadge,
  normalizePolygonCoordinates,
  validateCoordinates,
} from '../utils/web3';
import { CropCode, Policy, PolicyStatus, Region } from '../types';

interface FarmerViewProps {
  contract: ethers.Contract | null;
  account: string | null;
  policies: Policy[];
  onRefresh: () => void;
  showToast: (msg: string, type?: 'success' | 'error' | 'info') => void;
}

const PRESET_COORDS = {
  anantapur: '14.6812, 77.6000; 14.6850, 77.6000; 14.6850, 77.6050; 14.6812, 77.6050',
  kurnool: '15.8281, 78.0373; 15.8320, 78.0373; 15.8320, 78.0420; 15.8281, 78.0420',
  kadapa: '14.4673, 78.8242; 14.4710, 78.8242; 14.4710, 78.8290; 14.4673, 78.8290',
};

export const FarmerView: React.FC<FarmerViewProps> = ({
  contract,
  account,
  policies,
  onRefresh,
  showToast,
}) => {
  // Boundary Registration State
  const [coordsInput, setCoordsInput] = useState(PRESET_COORDS.anantapur);
  const [normalizedCoords, setNormalizedCoords] = useState('');
  const [computedLandHash, setComputedLandHash] = useState('');
  const [coordError, setCoordError] = useState<string | null>(null);
  const [isLandActiveOnChain, setIsLandActiveOnChain] = useState<boolean | null>(null);
  const [checkingLand, setCheckingLand] = useState(false);

  // Policy Purchase State
  const [selectedCrop, setSelectedCrop] = useState<CropCode>(CropCode.GROUNDNUT);
  const [selectedRegion, setSelectedRegion] = useState<Region>(Region.ANANTAPUR);
  const [sumInsuredEth, setSumInsuredEth] = useState('1.0');
  const [calculatedPremiumWei, setCalculatedPremiumWei] = useState<bigint>(0n);
  const [isPurchasing, setIsPurchasing] = useState(false);

  // Dispute State
  const [disputePolicyId, setDisputePolicyId] = useState<number | null>(null);
  const [disputeReason, setDisputeReason] = useState('');
  const [submittingDispute, setSubmittingDispute] = useState(false);

  // Parse and normalize boundary coordinates whenever input changes
  useEffect(() => {
    try {
      setCoordError(null);
      const normalized = normalizePolygonCoordinates(coordsInput);
      setNormalizedCoords(normalized);
      const hash = computeLandHash(coordsInput);
      setComputedLandHash(hash);

      // Validate centroid
      const firstVertex = coordsInput.split(/[;\n]/)[0].split(',');
      if (firstVertex.length >= 2) {
        const valRes = validateCoordinates(parseFloat(firstVertex[0]), parseFloat(firstVertex[1]));
        if (!valRes.valid) {
          setCoordError(valRes.error || 'Coordinates outside target zone');
        }
      }
    } catch (err: unknown) {
      setCoordError((err as Error).message);
      setNormalizedCoords('');
      setComputedLandHash('');
    }
  }, [coordsInput]);

  // Check on-chain activeLandHashes
  const checkCadastralRegistry = async () => {
    if (!contract || !computedLandHash) return;
    setCheckingLand(true);
    try {
      const isActive: boolean = await contract.activeLandHashes(computedLandHash);
      setIsLandActiveOnChain(isActive);
      if (isActive) {
        showToast('Warning: This parcel boundary is already insured on-chain!', 'error');
      } else {
        showToast('Parcel is clear for underwriting.', 'success');
      }
    } catch (err: unknown) {
      showToast(`Failed to query land registry: ${(err as Error).message}`, 'error');
    } finally {
      setCheckingLand(false);
    }
  };

  // Calculate live dynamic premium from contract
  useEffect(() => {
    if (!contract || !sumInsuredEth || isNaN(parseFloat(sumInsuredEth)) || parseFloat(sumInsuredEth) <= 0) {
      setCalculatedPremiumWei(0n);
      return;
    }
    const fetchPremium = async () => {
      try {
        const weiAmount = ethers.parseEther(sumInsuredEth);
        const premium: bigint = await contract.calculatePremium(weiAmount, selectedRegion);
        setCalculatedPremiumWei(premium);
      } catch {
        // Fallback calculation: (300 + regional_bps) / 10000
        const bps = selectedRegion === Region.ANANTAPUR ? 650 : selectedRegion === Region.KURNOOL ? 550 : 500;
        const wei = ethers.parseEther(sumInsuredEth);
        setCalculatedPremiumWei((wei * BigInt(bps)) / 10000n);
      }
    };
    fetchPremium();
  }, [contract, sumInsuredEth, selectedRegion]);

  // Purchase Policy
  const handlePurchasePolicy = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!contract || !account) {
      showToast('Please connect your MetaMask wallet first.', 'error');
      return;
    }
    if (!computedLandHash) {
      showToast('Please enter valid polygon coordinates.', 'error');
      return;
    }
    if (isLandActiveOnChain) {
      showToast('Cannot purchase: land parcel is already covered by an active policy.', 'error');
      return;
    }
    if (calculatedPremiumWei === 0n) {
      showToast('Please enter a valid positive sum insured.', 'error');
      return;
    }

    setIsPurchasing(true);
    try {
      const sumInsuredWei = ethers.parseEther(sumInsuredEth);
      const now = Math.floor(Date.now() / 1000);
      const endTime = now + 86400 * 120; // 120-day Kharif season

      const tx = await contract.createPolicy(
        computedLandHash,
        selectedCrop,
        selectedRegion,
        sumInsuredWei,
        now,
        endTime,
        DEFAULT_RULES_HASH,
        { value: calculatedPremiumWei }
      );

      showToast(`Transaction sent! Waiting for confirmation... Hash: ${tx.hash.slice(0, 10)}...`, 'info');
      await tx.wait();
      showToast('Policy created successfully!', 'success');
      onRefresh();
    } catch (err: unknown) {
      const msg = (err as Error).message;
      showToast(`Purchase failed: ${msg}`, 'error');
    } finally {
      setIsPurchasing(false);
    }
  };

  // Withdraw Payout
  const handleWithdrawPayout = async (policyId: number) => {
    if (!contract) return;
    try {
      const tx = await contract.withdrawPayout(policyId);
      showToast(`Withdrawal submitted! Tx: ${tx.hash.slice(0, 10)}...`, 'info');
      await tx.wait();
      showToast(`Payout for Policy #${policyId} successfully pulled to your wallet!`, 'success');
      onRefresh();
    } catch (err: unknown) {
      showToast(`Withdrawal failed: ${(err as Error).message}`, 'error');
    }
  };

  // Open Dispute
  const handleOpenDispute = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!contract || disputePolicyId === null || !disputeReason.trim()) return;
    setSubmittingDispute(true);
    try {
      const tx = await contract.openDispute(disputePolicyId, disputeReason.trim());
      showToast(`Dispute opened! Tx: ${tx.hash.slice(0, 10)}...`, 'info');
      await tx.wait();
      showToast(`Dispute filed for Policy #${disputePolicyId}. Escalated to review queue.`, 'success');
      setDisputePolicyId(null);
      setDisputeReason('');
      onRefresh();
    } catch (err: unknown) {
      showToast(`Failed to open dispute: ${(err as Error).message}`, 'error');
    } finally {
      setSubmittingDispute(false);
    }
  };

  // Filter policies belonging to connected farmer (or show all in demo mode)
  const farmerPolicies = account
    ? policies.filter((p) => p.farmer.toLowerCase() === account.toLowerCase() || policies.length <= 5)
    : policies;

  return (
    <div>
      <div className="grid-2">
        {/* Cadastral Boundary Registration */}
        <div className="card">
          <div className="card-title">
            <span>📍 Cadastral Land Registration</span>
          </div>
          <p className="card-desc">
            Define agricultural parcel polygon vertices. Coordinates are normalized to canonical precision
            and hashed in-browser to prevent duplicate land underwriting.
          </p>

          <div className="form-group">
            <label>Parcel Vertices (lat, lon pairs separated by semicolons):</label>
            <textarea
              className="form-control"
              rows={3}
              value={coordsInput}
              onChange={(e) => setCoordsInput(e.target.value)}
              placeholder="14.6812, 77.6000; 14.6850, 77.6000; 14.6850, 77.6050; 14.6812, 77.6050"
            />
            <div className="preset-strip">
              <button
                type="button"
                className="btn btn-sm btn-secondary"
                onClick={() => setCoordsInput(PRESET_COORDS.anantapur)}
              >
                Preset: Anantapur Groundnut
              </button>
              <button
                type="button"
                className="btn btn-sm btn-secondary"
                onClick={() => setCoordsInput(PRESET_COORDS.kurnool)}
              >
                Preset: Kurnool Groundnut
              </button>
              <button
                type="button"
                className="btn btn-sm btn-secondary"
                onClick={() => setCoordsInput(PRESET_COORDS.kadapa)}
              >
                Preset: Kadapa Groundnut
              </button>
            </div>
          </div>

          {coordError && <div className="alert-box alert-warning">⚠️ {coordError}</div>}

          {normalizedCoords && (
            <div style={{ marginBottom: '12px', fontSize: '0.85rem' }}>
              <div style={{ fontWeight: 600, color: '#475569' }}>Canonical Coordinate String:</div>
              <div style={{ fontFamily: 'monospace', wordBreak: 'break-all', background: '#f8fafc', padding: '6px' }}>
                {normalizedCoords}
              </div>
            </div>
          )}

          {computedLandHash && (
            <div style={{ marginBottom: '16px', fontSize: '0.85rem' }}>
              <div style={{ fontWeight: 600, color: '#475569' }}>In-Browser Keccak256 Land Hash:</div>
              <div style={{ fontFamily: 'monospace', wordBreak: 'break-all', color: '#0369a1' }}>
                {computedLandHash}
              </div>
            </div>
          )}

          <button
            type="button"
            className="btn btn-secondary"
            onClick={checkCadastralRegistry}
            disabled={!computedLandHash || checkingLand}
          >
            {checkingLand ? 'Querying Contract...' : '🔍 Check Cadastral Registry Availability'}
          </button>

          {isLandActiveOnChain !== null && (
            <div style={{ marginTop: '10px' }}>
              {isLandActiveOnChain ? (
                <span className="badge badge-review">❌ Occupied (Active Policy Exists)</span>
              ) : (
                <span className="badge badge-active">✔ Available for Underwriting</span>
              )}
            </div>
          )}
        </div>

        {/* Policy Purchase Card */}
        <div className="card">
          <div className="card-title">
            <span>🛡️ Buy Parametric Policy</span>
          </div>
          <p className="card-desc">
            District-based pricing incorporates baseline rate (3.0%) plus regional drought risk loading.
          </p>

          <form onSubmit={handlePurchasePolicy}>
            <div className="form-group">
              <label>Select Crop:</label>
              <select
                className="form-control"
                value={selectedCrop}
                onChange={(e) => setSelectedCrop(Number(e.target.value) as CropCode)}
              >
                <option value={CropCode.GROUNDNUT}>Groundnut (Kharif Rainfed)</option>
                <option value={CropCode.COTTON}>Cotton (Commercial)</option>
              </select>
            </div>

            <div className="form-group">
              <label>Target District / Region:</label>
              <select
                className="form-control"
                value={selectedRegion}
                onChange={(e) => setSelectedRegion(Number(e.target.value) as Region)}
              >
                <option value={Region.ANANTAPUR}>Anantapur (6.5% total rate: 3.0% base + 3.5% risk)</option>
                <option value={Region.KURNOOL}>Kurnool (5.5% total rate: 3.0% base + 2.5% risk)</option>
                <option value={Region.KADAPA}>Kadapa (5.0% total rate: 3.0% base + 2.0% risk)</option>
              </select>
            </div>

            <div className="form-group">
              <label>Sum Insured (ETH):</label>
              <input
                type="number"
                step="0.1"
                min="0.1"
                className="form-control"
                value={sumInsuredEth}
                onChange={(e) => setSumInsuredEth(e.target.value)}
                placeholder="1.0"
                required
              />
            </div>

            <div style={{ background: '#f8fafc', padding: '12px', borderRadius: '6px', marginBottom: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                <span style={{ fontSize: '0.85rem', color: '#64748b' }}>Dynamic Premium Due:</span>
                <span style={{ fontWeight: 700, color: '#0369a1' }}>{formatEth(calculatedPremiumWei)}</span>
              </div>
              <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
                Rules Commitment Hash: <span style={{ fontFamily: 'monospace' }}>{DEFAULT_RULES_HASH.slice(0, 10)}...</span>
              </div>
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              style={{ width: '100%' }}
              disabled={isPurchasing || !computedLandHash}
            >
              {isPurchasing ? 'Confirming Transaction...' : '📝 Underwrite & Pay Premium'}
            </button>
          </form>
        </div>
      </div>

      {/* Policies List */}
      <div className="card">
        <div className="card-title">
          <span>📜 Active & Historical Policies</span>
          <button className="btn btn-sm btn-secondary" onClick={onRefresh}>
            🔄 Refresh Policies
          </button>
        </div>

        {farmerPolicies.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '32px', color: '#64748b' }}>
            No policies found. Register a boundary above or run the demo seeder.
          </div>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>District / Crop</th>
                  <th>Sum Insured</th>
                  <th>Status</th>
                  <th>Oracle Reports (2-of-3)</th>
                  <th>Settled Tier / Payout</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {farmerPolicies.map((policy) => {
                  const statusInfo = getStatusBadge(policy.status);
                  const tierInfo = getTierBadge(policy.finalTier);
                  const isSettled = policy.status === PolicyStatus.SETTLED;
                  const canWithdraw = isSettled && policy.payoutAmount > 0n && !policy.payoutWithdrawn;

                  // 7-day dispute window countdown
                  const disputeDeadline = policy.settlementTime + 7 * 86400;
                  const nowSec = Math.floor(Date.now() / 1000);
                  const disputeWindowRemaining = disputeDeadline - nowSec;
                  const canDispute = isSettled && disputeWindowRemaining > 0;

                  return (
                    <tr key={policy.id}>
                      <td style={{ fontWeight: 700 }}>#{policy.id}</td>
                      <td>
                        <div style={{ fontWeight: 600 }}>{Region[policy.region]}</div>
                        <div style={{ fontSize: '0.75rem', color: '#64748b' }}>{CropCode[policy.crop]}</div>
                      </td>
                      <td>
                        <div>{formatEth(policy.sumInsured)}</div>
                        <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
                          Prem: {formatEth(policy.premium)}
                        </div>
                      </td>
                      <td>
                        <span className={`badge ${statusInfo.className}`}>{statusInfo.label}</span>
                        <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '2px' }}>
                          Matures: {formatTimestamp(policy.endTime)}
                        </div>
                      </td>
                      <td>
                        {policy.reports ? (
                          <div style={{ fontSize: '0.8rem', display: 'flex', flexDirection: 'column', gap: '2px' }}>
                            <span>
                              🌧️ Weather:{' '}
                              {policy.reports.weather.submitted ? (
                                <span className={`tier-badge ${getTierBadge(policy.reports.weather.tier).className}`}>
                                  Tier {policy.reports.weather.tier}
                                </span>
                              ) : (
                                <span style={{ color: '#94a3b8' }}>⏳ Pending</span>
                              )}
                            </span>
                            <span>
                              🛰️ Satellite:{' '}
                              {policy.reports.satellite.submitted ? (
                                <span className={`tier-badge ${getTierBadge(policy.reports.satellite.tier).className}`}>
                                  Tier {policy.reports.satellite.tier}
                                </span>
                              ) : (
                                <span style={{ color: '#94a3b8' }}>⏳ Pending</span>
                              )}
                            </span>
                            <span>
                              🌱 Soil:{' '}
                              {policy.reports.soil.submitted ? (
                                <span className={`tier-badge ${getTierBadge(policy.reports.soil.tier).className}`}>
                                  Tier {policy.reports.soil.tier}
                                </span>
                              ) : (
                                <span style={{ color: '#94a3b8' }}>⏳ Pending</span>
                              )}
                            </span>
                          </div>
                        ) : (
                          <span style={{ color: '#94a3b8', fontSize: '0.8rem' }}>Awaiting Season End</span>
                        )}
                      </td>
                      <td>
                        {isSettled ? (
                          <div>
                            <span className={`tier-badge ${tierInfo.className}`}>{tierInfo.label}</span>
                            <div style={{ fontWeight: 700, color: '#16a34a', marginTop: '4px' }}>
                              {formatEth(policy.payoutAmount)} ({tierInfo.payoutPct}%)
                            </div>
                            {policy.payoutWithdrawn && (
                              <div style={{ fontSize: '0.75rem', color: '#64748b' }}>✔ Withdrawn</div>
                            )}
                          </div>
                        ) : (
                          <span style={{ color: '#94a3b8', fontSize: '0.85rem' }}>—</span>
                        )}
                      </td>
                      <td>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                          {canWithdraw && (
                            <button
                              className="btn btn-sm btn-success"
                              onClick={() => handleWithdrawPayout(policy.id)}
                            >
                              💸 Withdraw Payout
                            </button>
                          )}

                          {canDispute && (
                            <button
                              className="btn btn-sm btn-secondary"
                              onClick={() => setDisputePolicyId(policy.id)}
                            >
                              ⚠️ Open Dispute ({Math.ceil(disputeWindowRemaining / 86400)}d left)
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Dispute Modal */}
      {disputePolicyId !== null && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
        >
          <div style={{ background: '#fff', padding: '24px', borderRadius: '8px', maxWidth: '480px', width: '90%' }}>
            <h3 style={{ marginBottom: '12px' }}>Open Dispute for Policy #{disputePolicyId}</h3>
            <p style={{ fontSize: '0.85rem', color: '#64748b', marginBottom: '16px' }}>
              Farmers may file a formal dispute within 7 days of settlement if localized physical conditions
              (e.g., severe cloud obstruction or rain-gauge misalignment) distorted the 2-of-3 consensus.
            </p>
            <form onSubmit={handleOpenDispute}>
              <div className="form-group">
                <label>Dispute Justification & Physical Evidence Note:</label>
                <textarea
                  className="form-control"
                  rows={3}
                  value={disputeReason}
                  onChange={(e) => setDisputeReason(e.target.value)}
                  placeholder="e.g. Localized satellite cloud cover distorted vegetation index peak..."
                  required
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setDisputePolicyId(null)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-danger"
                  disabled={submittingDispute || !disputeReason.trim()}
                >
                  {submittingDispute ? 'Submitting...' : 'Submit Formal Dispute'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
