import React from 'react';
import { formatEth } from '../utils/web3';
import { UserRoles } from '../types';

interface HeaderProps {
  account: string | null;
  balance: bigint;
  chainId: number | null;
  roles: UserRoles;
  activeTab: 'farmer' | 'admin' | 'dev';
  setActiveTab: (tab: 'farmer' | 'admin' | 'dev') => void;
  onConnect: () => void;
  onSwitchNetwork: () => void;
  contractAddress: string;
}

export const Header: React.FC<HeaderProps> = ({
  account,
  balance,
  chainId,
  roles,
  activeTab,
  setActiveTab,
  onConnect,
  onSwitchNetwork,
  contractAddress,
}) => {
  const isLocalNetwork = chainId === 31337;

  return (
    <header className="app-header">
      <div className="header-top">
        <div className="header-title">
          <h1>🌾 Crop Insurance Chain</h1>
          <p>Hardware-Free Parametric Blockchain Insurance • Andhra Pradesh (Rayalaseema)</p>
          <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '4px' }}>
            Contract: <span style={{ fontFamily: 'monospace' }}>{contractAddress}</span>
          </div>
        </div>

        <div className="header-actions">
          {account ? (
            <>
              {isLocalNetwork ? (
                <span className="network-pill network-local">Hardhat (31337)</span>
              ) : (
                <button className="btn btn-sm btn-danger" onClick={onSwitchNetwork}>
                  Switch to Chain 31337
                </button>
              )}

              <div className="wallet-badge">
                <span className="balance-pill">{formatEth(balance)}</span>
                <span>{account.slice(0, 6)}...{account.slice(-4)}</span>
              </div>
            </>
          ) : (
            <button className="btn btn-primary" onClick={onConnect}>
              Connect MetaMask
            </button>
          )}
        </div>
      </div>

      {account && (
        <div className="roles-strip">
          <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#64748b' }}>Active Roles:</span>
          {roles.isFarmer && <span className="role-tag">Farmer</span>}
          {roles.isAdmin && <span className="role-tag" style={{ background: '#fef3c7', color: '#b45309' }}>Admin</span>}
          {roles.isWeatherOracle && <span className="role-tag">Weather Oracle</span>}
          {roles.isSatelliteOracle && <span className="role-tag">Satellite Oracle</span>}
          {roles.isSoilOracle && <span className="role-tag">Soil Oracle</span>}
          {roles.isFraudChecker && <span className="role-tag">Fraud Checker</span>}
          {roles.isDisputeReviewer && <span className="role-tag">Dispute Reviewer</span>}
        </div>
      )}

      <nav className="nav-tabs" style={{ marginTop: '16px' }}>
        <button
          className={`tab-btn ${activeTab === 'farmer' ? 'active' : ''}`}
          onClick={() => setActiveTab('farmer')}
        >
          👨‍🌾 Farmer Portal
        </button>
        <button
          className={`tab-btn ${activeTab === 'admin' ? 'active' : ''}`}
          onClick={() => setActiveTab('admin')}
        >
          ⚖️ Admin & Oracles
        </button>
        <button
          className={`tab-btn ${activeTab === 'dev' ? 'active' : ''}`}
          onClick={() => setActiveTab('dev')}
        >
          🛠️ Dev & Simulation
        </button>
      </nav>
    </header>
  );
};
