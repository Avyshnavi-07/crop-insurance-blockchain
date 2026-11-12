import React, { useState } from 'react';
import { ethers } from 'ethers';
import { formatEth } from '../utils/web3';
import { CropCode, OracleSource, Policy, PolicyStatus, Region, SeverityTier, UserRoles } from '../types';

interface AdminViewProps {
  contract: ethers.Contract | null;
  account: string | null;
  roles: UserRoles;
  policies: Policy[];
  riskPoolBalance: bigint;
  reservedExposure: bigint;
  onRefresh: () => void;
  showToast: (msg: string, type?: 'success' | 'error' | 'info') => void;
}

export const AdminView: React.FC<AdminViewProps> = ({
  contract,
  account,
  roles,
  policies,
  riskPoolBalance,
  reservedExposure,
  onRefresh,
  showToast,
}) => {
  // Risk Pool State
  const [fundAmountEth, setFundAmountEth] = useState('');
  const [withdrawAmountEth, setWithdrawAmountEth] = useState('');
  const [selectedRiskRegion, setSelectedRiskRegion] = useState<Region>(Region.ANANTAPUR);
  const [regionalRiskBps, setRegionalRiskBps] = useState('350');
  const [isManagingPool, setIsManagingPool] = useState(false);

  // Oracle Submission State
  const [oraclePolicyId, setOraclePolicyId] = useState(policies[0]?.id || 1);
  const [oracleSource, setOracleSource] = useState<OracleSource>(OracleSource.WEATHER);
  const [oracleTier, setOracleTier] = useState<SeverityTier>(SeverityTier.MODERATE);
  const [isSubmittingReport, setIsSubmittingReport] = useState(false);

  // Review Queue State
  const [flagPolicyId, setFlagPolicyId] = useState('');
  const [flagReasonText, setFlagReasonText] = useState('Cadastral duplicate anomaly detected');
  const [isFlagging, setIsFlagging] = useState(false);

  const [disputeResolveId, setDisputeResolveId] = useState(
    policies.find((p) => p.status === PolicyStatus.DISPUTED)?.id || ''
  );
  const [disputeNewTier, setDisputeNewTier] = useState<SeverityTier>(SeverityTier.SEVERE);
  const [isResolvingDispute, setIsResolvingDispute] = useState(false);

  const [timeoutPolicyId, setTimeoutPolicyId] = useState('');
  const [isEscalatingTimeout, setIsEscalatingTimeout] = useState(false);

  const headroom = riskPoolBalance >= reservedExposure ? riskPoolBalance - reservedExposure : 0n;

  // 1. Fund Risk Pool
  const handleFundRiskPool = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!contract || !fundAmountEth) return;
    setIsManagingPool(true);
    try {
      const wei = ethers.parseEther(fundAmountEth);
      const tx = await contract.fundRiskPool({ value: wei });
      showToast(`Funding sent! Tx: ${tx.hash.slice(0, 10)}...`, 'info');
      await tx.wait();
      showToast(`Funded risk pool with ${fundAmountEth} ETH!`, 'success');
      setFundAmountEth('');
      onRefresh();
    } catch (err: unknown) {
      showToast(`Funding failed: ${(err as Error).message}`, 'error');
    } finally {
      setIsManagingPool(false);
    }
  };

  // 2. Withdraw Risk Pool
  const handleWithdrawRiskPool = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!contract || !withdrawAmountEth) return;
    setIsManagingPool(true);
    try {
      const wei = ethers.parseEther(withdrawAmountEth);
      const tx = await contract.withdrawRiskPool(wei);
      showToast(`Withdrawal sent! Tx: ${tx.hash.slice(0, 10)}...`, 'info');
      await tx.wait();
      showToast(`Withdrew ${withdrawAmountEth} ETH from pool!`, 'success');
      setWithdrawAmountEth('');
      onRefresh();
    } catch (err: unknown) {
      showToast(`Withdrawal failed: ${(err as Error).message}`, 'error');
    } finally {
      setIsManagingPool(false);
    }
  };

  // 3. Set Regional Risk Rate
  const handleSetRegionalRisk = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!contract || !regionalRiskBps) return;
    setIsManagingPool(true);
    try {
      const bps = parseInt(regionalRiskBps, 10);
      const tx = await contract.setRegionalRiskBps(selectedRiskRegion, bps);
      showToast(`Rate update sent! Tx: ${tx.hash.slice(0, 10)}...`, 'info');
      await tx.wait();
      showToast(`Updated regional risk for ${Region[selectedRiskRegion]} to ${bps} bps!`, 'success');
      onRefresh();
    } catch (err: unknown) {
      showToast(`Rate update failed: ${(err as Error).message}`, 'error');
    } finally {
      setIsManagingPool(false);
    }
  };

  // 4. Submit Oracle Report
  const handleSubmitReport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!contract) return;
    setIsSubmittingReport(true);
    try {
      const tx = await contract.submitReport(oraclePolicyId, oracleSource, oracleTier);
      showToast(`Oracle assessment sent! Tx: ${tx.hash.slice(0, 10)}...`, 'info');
      await tx.wait();
      showToast(`Submitted ${OracleSource[oracleSource]} report for Policy #${oraclePolicyId}!`, 'success');
      onRefresh();
    } catch (err: unknown) {
      showToast(`Report submission failed: ${(err as Error).message}`, 'error');
    } finally {
      setIsSubmittingReport(false);
    }
  };

  // 5. Flag Fraud
  const handleFlagFraud = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!contract || !flagPolicyId) return;
    setIsFlagging(true);
    try {
      const reasonHash = ethers.keccak256(ethers.toUtf8Bytes(flagReasonText.trim()));
      const tx = await contract.flagFraud(parseInt(flagPolicyId, 10), reasonHash);
      showToast(`Fraud flag sent! Tx: ${tx.hash.slice(0, 10)}...`, 'info');
      await tx.wait();
      showToast(`Policy #${flagPolicyId} moved to UNDER_REVIEW!`, 'success');
      setFlagPolicyId('');
      onRefresh();
    } catch (err: unknown) {
      showToast(`Flag fraud failed: ${(err as Error).message}`, 'error');
    } finally {
      setIsFlagging(false);
    }
  };

  // 6. Escalate Timeout
  const handleEscalateTimeout = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!contract || !timeoutPolicyId) return;
    setIsEscalatingTimeout(true);
    try {
      const tx = await contract.escalateTimeout(parseInt(timeoutPolicyId, 10));
      showToast(`Escalation sent! Tx: ${tx.hash.slice(0, 10)}...`, 'info');
      await tx.wait();
      showToast(`Policy #${timeoutPolicyId} escalated to UNDER_REVIEW due to oracle timeout.`, 'success');
      setTimeoutPolicyId('');
      onRefresh();
    } catch (err: unknown) {
      showToast(`Escalate timeout failed: ${(err as Error).message}`, 'error');
    } finally {
      setIsEscalatingTimeout(false);
    }
  };

  // 7. Resolve Dispute
  const handleResolveDispute = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!contract || !disputeResolveId) return;
    setIsResolvingDispute(true);
    try {
      const tx = await contract.resolveDispute(parseInt(String(disputeResolveId), 10), disputeNewTier);
      showToast(`Dispute resolution sent! Tx: ${tx.hash.slice(0, 10)}...`, 'info');
      await tx.wait();
      showToast(`Dispute for Policy #${disputeResolveId} resolved to ${SeverityTier[disputeNewTier]}!`, 'success');
      onRefresh();
    } catch (err: unknown) {
      showToast(`Dispute resolution failed: ${(err as Error).message}`, 'error');
    } finally {
      setIsResolvingDispute(false);
    }
  };

  // Review Queue items: policies under review or disputed
  const reviewPolicies = policies.filter(
    (p) => p.status === PolicyStatus.UNDER_REVIEW || p.status === PolicyStatus.DISPUTED
  );

  return (
    <div>
      {account && (
        <div className="alert-box alert-info" style={{ marginBottom: '16px' }}>
          <div>
            <strong>Connected Operator:</strong> <span style={{ fontFamily: 'monospace' }}>{account}</span>
          </div>
          <div style={{ fontSize: '0.8rem', marginTop: '4px' }}>
            Active Privileges:{' '}
            {[
              roles.isAdmin && 'Admin',
              roles.isFraudChecker && 'Fraud Checker',
              roles.isDisputeReviewer && 'Dispute Reviewer',
              roles.isWeatherOracle && 'Weather Oracle',
              roles.isSatelliteOracle && 'Satellite Oracle',
              roles.isSoilOracle && 'Soil Oracle',
            ]
              .filter(Boolean)
              .join(' • ') || 'Standard Farmer / Observer'}
          </div>
        </div>
      )}

      {/* Solvency & Risk Pool Overview */}
      <div className="card">
        <div className="card-title">
          <span>🏦 Solvency Pool & Underwriting Exposure</span>
          <button className="btn btn-sm btn-secondary" onClick={onRefresh}>
            🔄 Refresh
          </button>
        </div>
        <p className="card-desc">
          Verifies smart contract solvency invariant: riskPoolBalance + premium ≥ reservedExposure + sumInsured.
        </p>

        <div className="stat-grid">
          <div className="stat-box">
            <div className="stat-label">Total Risk Pool Balance</div>
            <div className="stat-value" style={{ color: '#0369a1' }}>{formatEth(riskPoolBalance)}</div>
          </div>
          <div className="stat-box">
            <div className="stat-label">Reserved Exposure</div>
            <div className="stat-value" style={{ color: '#d97706' }}>{formatEth(reservedExposure)}</div>
          </div>
          <div className="stat-box">
            <div className="stat-label">Available Solvency Headroom</div>
            <div className="stat-value" style={{ color: '#16a34a' }}>{formatEth(headroom)}</div>
          </div>
        </div>

        <div className="grid-2" style={{ marginBottom: 0 }}>
          {/* Fund / Withdraw Pool */}
          <div>
            <form onSubmit={handleFundRiskPool} style={{ marginBottom: '16px' }}>
              <div className="form-group">
                <label>Fund Risk Pool (ETH):</label>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <input
                    type="number"
                    step="0.5"
                    min="0.1"
                    className="form-control"
                    placeholder="e.g. 10.0"
                    value={fundAmountEth}
                    onChange={(e) => setFundAmountEth(e.target.value)}
                  />
                  <button type="submit" className="btn btn-success" disabled={isManagingPool || !fundAmountEth}>
                    Fund
                  </button>
                </div>
              </div>
            </form>

            <form onSubmit={handleWithdrawRiskPool}>
              <div className="form-group">
                <label>Withdraw Solvency Surplus (ETH):</label>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <input
                    type="number"
                    step="0.5"
                    min="0.1"
                    className="form-control"
                    placeholder="e.g. 5.0"
                    value={withdrawAmountEth}
                    onChange={(e) => setWithdrawAmountEth(e.target.value)}
                  />
                  <button type="submit" className="btn btn-secondary" disabled={isManagingPool || !withdrawAmountEth}>
                    Withdraw
                  </button>
                </div>
              </div>
            </form>
          </div>

          {/* Regional Risk Adjustment */}
          <div>
            <form onSubmit={handleSetRegionalRisk}>
              <div className="form-group">
                <label>Set District Risk Rate:</label>
                <select
                  className="form-control"
                  style={{ marginBottom: '8px' }}
                  value={selectedRiskRegion}
                  onChange={(e) => setSelectedRiskRegion(Number(e.target.value) as Region)}
                >
                  <option value={Region.ANANTAPUR}>Anantapur (Current baseline: 350 bps / 3.5%)</option>
                  <option value={Region.KURNOOL}>Kurnool (Current baseline: 250 bps / 2.5%)</option>
                  <option value={Region.KADAPA}>Kadapa (Current baseline: 200 bps / 2.0%)</option>
                </select>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <input
                    type="number"
                    step="10"
                    className="form-control"
                    placeholder="e.g. 350 bps"
                    value={regionalRiskBps}
                    onChange={(e) => setRegionalRiskBps(e.target.value)}
                  />
                  <button type="submit" className="btn btn-primary" disabled={isManagingPool}>
                    Update BPS
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      </div>

      <div className="grid-2">
        {/* Oracle Assessment Submission */}
        <div className="card">
          <div className="card-title">
            <span>📡 Multi-Oracle Submission Portal</span>
          </div>
          <p className="card-desc">
            Authorized oracles (Weather, Satellite, Soil) submit independent severity assessments after season end.
          </p>

          <form onSubmit={handleSubmitReport}>
            <div className="form-group">
              <label>Select Target Policy:</label>
              <select
                className="form-control"
                value={oraclePolicyId}
                onChange={(e) => setOraclePolicyId(Number(e.target.value))}
              >
                {policies.map((p) => (
                  <option key={p.id} value={p.id}>
                    Policy #{p.id} ({Region[p.region]} - {PolicyStatus[p.status]})
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label>Oracle Source:</label>
              <select
                className="form-control"
                value={oracleSource}
                onChange={(e) => setOracleSource(Number(e.target.value) as OracleSource)}
              >
                <option value={OracleSource.WEATHER}>Weather Oracle (Open-Meteo Rainfall Deficit)</option>
                <option value={OracleSource.SATELLITE}>Satellite Oracle (Sentinel-2 NDVI Anomaly)</option>
                <option value={OracleSource.SOIL}>Soil Oracle (NASA SMAP Soil Moisture Deficit)</option>
              </select>
            </div>

            <div className="form-group">
              <label>Assessed Severity Tier:</label>
              <select
                className="form-control"
                value={oracleTier}
                onChange={(e) => setOracleTier(Number(e.target.value) as SeverityTier)}
              >
                <option value={SeverityTier.NONE}>None (Tier 0 - 0% Payout)</option>
                <option value={SeverityTier.MODERATE}>Moderate (Tier 1 - 25% Payout)</option>
                <option value={SeverityTier.SEVERE}>Severe (Tier 2 - 50% Payout)</option>
                <option value={SeverityTier.CATASTROPHIC}>Catastrophic (Tier 3 - 100% Payout)</option>
              </select>
            </div>

            <button type="submit" className="btn btn-primary" style={{ width: '100%' }} disabled={isSubmittingReport}>
              {isSubmittingReport ? 'Submitting Report...' : '📤 Submit Oracle Report'}
            </button>
          </form>
        </div>

        {/* Fraud Flagging & Timeout Escalation */}
        <div className="card">
          <div className="card-title">
            <span>🚨 Fraud Checker & Timeout Escalation</span>
          </div>
          <p className="card-desc">
            Inspect policies before payout. Flag suspicious claims to halt settlement or escalate unfulfilled oracles.
          </p>

          <form onSubmit={handleFlagFraud} style={{ marginBottom: '20px' }}>
            <div className="form-group">
              <label>Flag Policy for Fraud / Anomaly:</label>
              <div style={{ display: 'flex', gap: '8px', marginBottom: '8px' }}>
                <input
                  type="number"
                  min="1"
                  className="form-control"
                  style={{ maxWidth: '120px' }}
                  placeholder="Policy ID"
                  value={flagPolicyId}
                  onChange={(e) => setFlagPolicyId(e.target.value)}
                />
                <input
                  type="text"
                  className="form-control"
                  placeholder="Reason (hashed to bytes32)"
                  value={flagReasonText}
                  onChange={(e) => setFlagReasonText(e.target.value)}
                />
              </div>
              <button type="submit" className="btn btn-danger btn-sm" disabled={isFlagging || !flagPolicyId}>
                {isFlagging ? 'Flagging...' : 'Flag as UNDER_REVIEW'}
              </button>
            </div>
          </form>

          <form onSubmit={handleEscalateTimeout}>
            <div className="form-group">
              <label>Escalate Oracle Timeout (14 Days Post-Season):</label>
              <div style={{ display: 'flex', gap: '8px' }}>
                <input
                  type="number"
                  min="1"
                  className="form-control"
                  style={{ maxWidth: '140px' }}
                  placeholder="Policy ID"
                  value={timeoutPolicyId}
                  onChange={(e) => setTimeoutPolicyId(e.target.value)}
                />
                <button
                  type="submit"
                  className="btn btn-secondary btn-sm"
                  disabled={isEscalatingTimeout || !timeoutPolicyId}
                >
                  {isEscalatingTimeout ? 'Escalating...' : 'Escalate Timeout'}
                </button>
              </div>
            </div>
          </form>
        </div>
      </div>

      {/* Review & Dispute Queue */}
      <div className="card">
        <div className="card-title">
          <span>⚖️ Review Queue & Dispute Adjudication</span>
        </div>
        <p className="card-desc">
          Manage policies currently marked as UNDER_REVIEW or DISPUTED. Adjudicate payout upgrades after review.
        </p>

        {reviewPolicies.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '24px', color: '#64748b' }}>
            No policies currently in review or disputed status.
          </div>
        ) : (
          <div className="table-wrapper" style={{ marginBottom: '20px' }}>
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Farmer</th>
                  <th>District / Crop</th>
                  <th>Sum Insured</th>
                  <th>Status</th>
                  <th>Final Settled Tier</th>
                </tr>
              </thead>
              <tbody>
                {reviewPolicies.map((p) => (
                  <tr key={p.id}>
                    <td style={{ fontWeight: 700 }}>#{p.id}</td>
                    <td style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>
                      {p.farmer.slice(0, 8)}...{p.farmer.slice(-6)}
                    </td>
                    <td>{Region[p.region]} - {CropCode[p.crop]}</td>
                    <td>{formatEth(p.sumInsured)}</td>
                    <td>
                      <span className={`badge ${p.status === PolicyStatus.DISPUTED ? 'badge-disputed' : 'badge-review'}`}>
                        {PolicyStatus[p.status]}
                      </span>
                    </td>
                    <td>{SeverityTier[p.finalTier]} ({formatEth(p.payoutAmount)})</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Dispute Resolution Form */}
        <form onSubmit={handleResolveDispute} style={{ background: '#f8fafc', padding: '16px', borderRadius: '6px' }}>
          <div style={{ fontWeight: 600, marginBottom: '8px' }}>Adjudicate & Resolve Formal Dispute:</div>
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <div className="form-group" style={{ marginBottom: 0, minWidth: '140px' }}>
              <label>Disputed Policy ID:</label>
              <input
                type="number"
                min="1"
                className="form-control"
                placeholder="Policy ID"
                value={disputeResolveId}
                onChange={(e) => setDisputeResolveId(e.target.value)}
                required
              />
            </div>

            <div className="form-group" style={{ marginBottom: 0, minWidth: '200px' }}>
              <label>Adjudicated New Tier:</label>
              <select
                className="form-control"
                value={disputeNewTier}
                onChange={(e) => setDisputeNewTier(Number(e.target.value) as SeverityTier)}
              >
                <option value={SeverityTier.NONE}>Tier 0: None (0%)</option>
                <option value={SeverityTier.MODERATE}>Tier 1: Moderate (25%)</option>
                <option value={SeverityTier.SEVERE}>Tier 2: Severe (50%)</option>
                <option value={SeverityTier.CATASTROPHIC}>Tier 3: Catastrophic (100%)</option>
              </select>
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              disabled={isResolvingDispute || !disputeResolveId}
            >
              {isResolvingDispute ? 'Resolving...' : '⚖️ Execute Dispute Resolution'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
