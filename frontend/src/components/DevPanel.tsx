import React, { useState } from 'react';
import { ethers } from 'ethers';
import configData from '../config.json';
import { OracleSource, Policy, SeverityTier } from '../types';

interface DevPanelProps {
  contract: ethers.Contract | null;
  policies: Policy[];
  onRefresh: () => void;
  showToast: (msg: string, type?: 'success' | 'error' | 'info') => void;
}

export const DevPanel: React.FC<DevPanelProps> = ({
  contract,
  policies,
  onRefresh,
  showToast,
}) => {
  const [targetPolicyId, setTargetPolicyId] = useState(policies[0]?.id || 1);
  const [isAdvancingTime, setIsAdvancingTime] = useState(false);
  const [isBatchRunning, setIsBatchRunning] = useState(false);

  // Hardhat EVM Time Travel
  const advanceEvmTime = async (seconds: number, label: string) => {
    if (!window.ethereum) {
      showToast('MetaMask / Ethereum provider not detected.', 'error');
      return;
    }
    setIsAdvancingTime(true);
    try {
      const provider = new ethers.BrowserProvider(window.ethereum);
      await provider.send('evm_increaseTime', [seconds]);
      await provider.send('evm_mine', []);
      showToast(`Time traveled forward by ${label}!`, 'success');
      onRefresh();
    } catch (err: unknown) {
      showToast(`EVM time travel failed: ${(err as Error).message}`, 'error');
    } finally {
      setIsAdvancingTime(false);
    }
  };

  // Batch Honest Oracle Submission (2-of-3 Agreement)
  const handleBatchHonestSettlement = async () => {
    if (!contract) return;
    setIsBatchRunning(true);
    try {
      showToast(`Executing 2-of-3 consensus settlement for Policy #${targetPolicyId}...`, 'info');

      // Submit 3 honest reports assessing Tier 2 (Severe)
      const tx1 = await contract.submitReport(targetPolicyId, OracleSource.WEATHER, SeverityTier.SEVERE);
      await tx1.wait();
      const tx2 = await contract.submitReport(targetPolicyId, OracleSource.SATELLITE, SeverityTier.SEVERE);
      await tx2.wait();
      const tx3 = await contract.submitReport(targetPolicyId, OracleSource.SOIL, SeverityTier.SEVERE);
      await tx3.wait();

      const txSettle = await contract.settlePolicy(targetPolicyId);
      await txSettle.wait();

      showToast(`Policy #${targetPolicyId} settled via 2-of-3 consensus at Tier 2 (50% payout)!`, 'success');
      onRefresh();
    } catch (err: unknown) {
      showToast(`Settlement failed: ${(err as Error).message}`, 'error');
    } finally {
      setIsBatchRunning(false);
    }
  };

  // Batch Differing Oracle Submission (Median Fallback)
  const handleBatchMedianFallback = async () => {
    if (!contract) return;
    setIsBatchRunning(true);
    try {
      showToast(`Executing median fallback settlement for Policy #${targetPolicyId}...`, 'info');

      // Weather = Tier 1 (Moderate), Satellite = Tier 3 (Catastrophic), Soil = Tier 2 (Severe)
      // Sorted: [1, 2, 3] -> Median is 2 (50% payout)
      const tx1 = await contract.submitReport(targetPolicyId, OracleSource.WEATHER, SeverityTier.MODERATE);
      await tx1.wait();
      const tx2 = await contract.submitReport(targetPolicyId, OracleSource.SATELLITE, SeverityTier.CATASTROPHIC);
      await tx2.wait();
      const tx3 = await contract.submitReport(targetPolicyId, OracleSource.SOIL, SeverityTier.SEVERE);
      await tx3.wait();

      const txSettle = await contract.settlePolicy(targetPolicyId);
      await txSettle.wait();

      showToast(
        `Policy #${targetPolicyId} settled via Median Fallback! Reports: [1, 3, 2] -> Median = Tier 2 (50% payout).`,
        'success'
      );
      onRefresh();
    } catch (err: unknown) {
      showToast(`Median settlement failed: ${(err as Error).message}`, 'error');
    } finally {
      setIsBatchRunning(false);
    }
  };

  return (
    <div>
      <div className="grid-2">
        {/* EVM Time Travel Controls */}
        <div className="card">
          <div className="card-title">
            <span>⏳ Hardhat EVM Time Machine</span>
          </div>
          <p className="card-desc">
            Advance local blockchain timestamp to simulate seasonal maturation, oracle timeout, or dispute expiry.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <button
              className="btn btn-secondary"
              onClick={() => advanceEvmTime(86400, '1 Day (+86,400s)')}
              disabled={isAdvancingTime}
            >
              ⏩ Advance +1 Day
            </button>
            <button
              className="btn btn-secondary"
              onClick={() => advanceEvmTime(86400 * 15, '15 Days (Season End / Maturity)')}
              disabled={isAdvancingTime}
            >
              ⏭️ Advance +15 Days (Trigger Season Maturity)
            </button>
            <button
              className="btn btn-secondary"
              onClick={() => advanceEvmTime(86400 * 8, '8 Days (Dispute Expiry)')}
              disabled={isAdvancingTime}
            >
              🛑 Advance +8 Days (Expire 7-Day Dispute Window)
            </button>
          </div>
        </div>

        {/* Demo Consensus & Median Fallback Simulator */}
        <div className="card">
          <div className="card-title">
            <span>🔬 Rapid Settlement & Median Simulator</span>
          </div>
          <p className="card-desc">
            Execute batch oracle reports and settlement on-chain in one click to verify consensus mechanics.
          </p>

          <div className="form-group">
            <label>Select Target Policy:</label>
            <select
              className="form-control"
              value={targetPolicyId}
              onChange={(e) => setTargetPolicyId(Number(e.target.value))}
            >
              {policies.map((p) => (
                <option key={p.id} value={p.id}>
                  Policy #{p.id} ({p.farmer.slice(0, 8)}... - status: {p.status})
                </option>
              ))}
            </select>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <button
              className="btn btn-primary"
              onClick={handleBatchHonestSettlement}
              disabled={isBatchRunning}
            >
              ✔ Demo 2-of-3 Consensus (All Agree: Tier 2)
            </button>

            <button
              className="btn btn-secondary"
              onClick={handleBatchMedianFallback}
              disabled={isBatchRunning}
            >
              ⚖️ Demo Median Fallback (Tiers 1, 3, 2 -&gt; Median Tier 2)
            </button>
          </div>
        </div>
      </div>

      {/* Test Accounts Credentials for MetaMask */}
      <div className="card">
        <div className="card-title">
          <span>🔑 Local Hardhat Accounts & Role Credentials</span>
        </div>
        <p className="card-desc">
          Import these test private keys into MetaMask on chainId 31337 to switch between Farmer, Admin, and Oracle roles.
        </p>

        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Role</th>
                <th>Public Address</th>
                <th>Private Key (Hardhat Testnet Only)</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(configData.accounts).map(([name, acc]) => (
                <tr key={name}>
                  <td style={{ fontWeight: 600 }}>{name}</td>
                  <td style={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>{acc.address}</td>
                  <td>
                    <button
                      className="btn btn-sm btn-secondary"
                      onClick={() => {
                        const key = (acc as { privateKey?: string }).privateKey;
                        if (key) {
                          navigator.clipboard.writeText(key);
                          showToast(`Copied ${name} private key to clipboard!`, 'info');
                        }
                      }}
                    >
                      📋 Copy Key
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
