import React, { useEffect, useState, useCallback } from 'react';
import { ethers } from 'ethers';
import CropInsuranceAbi from './abi/CropInsurance.json';
import configData from './config.json';
import { Header } from './components/Header';
import { FarmerView } from './components/FarmerView';
import { AdminView } from './components/AdminView';
import { DevPanel } from './components/DevPanel';
import { Policy, UserRoles, PolicyReports } from './types';
import { decodeContractError } from './utils/web3';
import './styles.css';

interface Toast {
  id: number;
  message: string;
  type: 'success' | 'error' | 'info';
}

declare global {
  interface Window {
    ethereum?: ethers.Eip1193Provider & {
      on: (event: string, handler: (...args: unknown[]) => void) => void;
      removeListener: (event: string, handler: (...args: unknown[]) => void) => void;
      request: (args: { method: string; params?: unknown[] }) => Promise<unknown>;
    };
  }
}

export const App: React.FC = () => {
  const [account, setAccount] = useState<string | null>(null);
  const [balance, setBalance] = useState<bigint>(0n);
  const [chainId, setChainId] = useState<number | null>(null);
  const [contract, setContract] = useState<ethers.Contract | null>(null);
  const [readOnlyContract, setReadOnlyContract] = useState<ethers.Contract | null>(null);
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [riskPoolBalance, setRiskPoolBalance] = useState<bigint>(0n);
  const [reservedExposure, setReservedExposure] = useState<bigint>(0n);
  const [activeTab, setActiveTab] = useState<'farmer' | 'admin' | 'dev'>('farmer');
  const [toasts, setToasts] = useState<Toast[]>([]);

  const [roles, setRoles] = useState<UserRoles>({
    isAdmin: false,
    isWeatherOracle: false,
    isSatelliteOracle: false,
    isSoilOracle: false,
    isFraudChecker: false,
    isDisputeReviewer: false,
    isFarmer: true,
  });

  const showToast = useCallback((message: string, type: 'success' | 'error' | 'info' = 'info') => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4500);
  }, []);

  // Initialize Read-Only Fallback Provider
  useEffect(() => {
    try {
      const readProvider = new ethers.JsonRpcProvider(configData.rpcUrl);
      const c = new ethers.Contract(configData.contractAddress, CropInsuranceAbi.abi, readProvider);
      setReadOnlyContract(c);
    } catch (err: unknown) {
      console.warn('Could not initialize local read-only provider:', err);
    }
  }, []);

  // Check roles for connected account
  const updateRoles = useCallback(async (addr: string, c: ethers.Contract) => {
    try {
      const adminRole = '0x0000000000000000000000000000000000000000000000000000000000000000';
      const weatherRole = ethers.keccak256(ethers.toUtf8Bytes('ORACLE_WEATHER_ROLE'));
      const satelliteRole = ethers.keccak256(ethers.toUtf8Bytes('ORACLE_SATELLITE_ROLE'));
      const soilRole = ethers.keccak256(ethers.toUtf8Bytes('ORACLE_SOIL_ROLE'));
      const fraudRole = ethers.keccak256(ethers.toUtf8Bytes('FRAUD_CHECKER_ROLE'));
      const disputeRole = ethers.keccak256(ethers.toUtf8Bytes('DISPUTE_REVIEWER_ROLE'));

      const [isAdmin, isWeather, isSat, isSoil, isFraud, isDispute] = await Promise.all([
        c.hasRole(adminRole, addr).catch(() => false),
        c.hasRole(weatherRole, addr).catch(() => false),
        c.hasRole(satelliteRole, addr).catch(() => false),
        c.hasRole(soilRole, addr).catch(() => false),
        c.hasRole(fraudRole, addr).catch(() => false),
        c.hasRole(disputeRole, addr).catch(() => false),
      ]);

      setRoles({
        isAdmin,
        isWeatherOracle: isWeather,
        isSatelliteOracle: isSat,
        isSoilOracle: isSoil,
        isFraudChecker: isFraud,
        isDisputeReviewer: isDispute,
        isFarmer: true,
      });
    } catch (err) {
      console.error('Error fetching roles:', err);
    }
  }, []);

  // Fetch policies and risk pool balances
  const refreshData = useCallback(async () => {
    const targetContract = contract || readOnlyContract;
    if (!targetContract) return;

    try {
      // 1. Fetch risk pool balances
      const [poolBal, exposure, nextId] = await Promise.all([
        targetContract.riskPoolBalance().catch(() => 0n),
        targetContract.reservedExposure().catch(() => 0n),
        targetContract.nextPolicyId().catch(() => 1n),
      ]);

      setRiskPoolBalance(poolBal);
      setReservedExposure(exposure);

      // 2. Fetch policies
      const totalPolicies = Number(nextId) - 1;
      const loaded: Policy[] = [];

      for (let i = 1; i <= totalPolicies; i++) {
        try {
          const raw = await targetContract.policies(i);
          let reports: PolicyReports | undefined = undefined;

          try {
            const rawReports = await targetContract.getOracleReports(i);
            reports = {
              weather: { submitted: rawReports[0].submitted, tier: Number(rawReports[0].tier) },
              satellite: { submitted: rawReports[1].submitted, tier: Number(rawReports[1].tier) },
              soil: { submitted: rawReports[2].submitted, tier: Number(rawReports[2].tier) },
            };
          } catch {
            // Oracle reports not accessible yet
          }

          loaded.push({
            id: Number(raw.id),
            farmer: raw.farmer,
            landHash: raw.landHash,
            crop: Number(raw.crop),
            region: Number(raw.region),
            sumInsured: raw.sumInsured,
            premium: raw.premium,
            startTime: Number(raw.startTime),
            endTime: Number(raw.endTime),
            settlementTime: Number(raw.settlementTime),
            rulesHash: raw.rulesHash,
            status: Number(raw.status),
            finalTier: Number(raw.finalTier),
            payoutAmount: raw.payoutAmount,
            payoutWithdrawn: raw.payoutWithdrawn,
            reports,
          });
        } catch (e) {
          console.warn(`Could not load policy #${i}:`, e);
        }
      }

      setPolicies(loaded);
    } catch (err) {
      console.error('Refresh data error:', err);
    }
  }, [contract, readOnlyContract]);

  // Connect Wallet
  const connectWallet = useCallback(async () => {
    if (!window.ethereum) {
      showToast('MetaMask not detected. Running in read-only mode.', 'info');
      return;
    }

    try {
      const provider = new ethers.BrowserProvider(window.ethereum);
      const accounts = await provider.send('eth_requestAccounts', []);
      const net = await provider.getNetwork();
      const currentChainId = Number(net.chainId);
      setChainId(currentChainId);

      if (accounts.length > 0) {
        const userAddr = accounts[0];
        setAccount(userAddr);
        const bal = await provider.getBalance(userAddr);
        setBalance(bal);

        const signer = await provider.getSigner();
        const activeC = new ethers.Contract(configData.contractAddress, CropInsuranceAbi.abi, signer);
        setContract(activeC);
        updateRoles(userAddr, activeC);
        showToast(`Connected wallet: ${userAddr.slice(0, 6)}...${userAddr.slice(-4)}`, 'success');
      }
    } catch (err: unknown) {
      showToast(`Connection failed: ${decodeContractError(err)}`, 'error');
    }
  }, [showToast, updateRoles]);

  // Switch to Hardhat Local (Chain 31337)
  const switchToHardhat = useCallback(async () => {
    if (!window.ethereum) return;
    try {
      await window.ethereum.request({
        method: 'wallet_switchEthereumChain',
        params: [{ chainId: '0x7a69' }], // 31337 in hex
      });
      setChainId(31337);
      showToast('Switched to Hardhat Local (Chain 31337)!', 'success');
      connectWallet();
    } catch (switchError: unknown) {
      const err = switchError as { code?: number };
      if (err.code === 4902) {
        try {
          await window.ethereum.request({
            method: 'wallet_addEthereumChain',
            params: [
              {
                chainId: '0x7a69',
                chainName: 'Hardhat Localhost',
                rpcUrls: ['http://127.0.0.1:8545'],
                nativeCurrency: { name: 'Ether', symbol: 'ETH', decimals: 18 },
              },
            ],
          });
          setChainId(31337);
          showToast('Added and switched to Hardhat Localhost!', 'success');
          connectWallet();
        } catch (addError) {
          showToast(`Could not add network: ${(addError as Error).message}`, 'error');
        }
      } else {
        showToast(`Network switch failed: ${(switchError as Error).message}`, 'error');
      }
    }
  }, [connectWallet, showToast]);

  // Initial load and event listeners
  useEffect(() => {
    refreshData();

    if (window.ethereum) {
      const handleAccountsChanged = (accounts: unknown) => {
        const accs = accounts as string[];
        if (accs.length > 0) {
          setAccount(accs[0]);
          connectWallet();
        } else {
          setAccount(null);
          setContract(null);
        }
      };

      const handleChainChanged = () => {
        connectWallet();
      };

      window.ethereum.on('accountsChanged', handleAccountsChanged);
      window.ethereum.on('chainChanged', handleChainChanged);

      return () => {
        window.ethereum?.removeListener('accountsChanged', handleAccountsChanged);
        window.ethereum?.removeListener('chainChanged', handleChainChanged);
      };
    }
  }, [connectWallet, refreshData]);

  const activeContract = contract || readOnlyContract;

  return (
    <div className="app-container">
      <Header
        account={account}
        balance={balance}
        chainId={chainId}
        roles={roles}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onConnect={connectWallet}
        onSwitchNetwork={switchToHardhat}
        contractAddress={configData.contractAddress}
      />

      {activeTab === 'farmer' && (
        <FarmerView
          contract={activeContract}
          account={account}
          policies={policies}
          onRefresh={refreshData}
          showToast={showToast}
        />
      )}

      {activeTab === 'admin' && (
        <AdminView
          contract={activeContract}
          account={account}
          roles={roles}
          policies={policies}
          riskPoolBalance={riskPoolBalance}
          reservedExposure={reservedExposure}
          onRefresh={refreshData}
          showToast={showToast}
        />
      )}

      {activeTab === 'dev' && (
        <DevPanel
          contract={activeContract}
          policies={policies}
          onRefresh={refreshData}
          showToast={showToast}
        />
      )}

      {/* Toast Notification Container */}
      <div className="toast-container">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.type}`}>
            <span>{t.message}</span>
            <button
              style={{ background: 'none', border: 'none', cursor: 'pointer', fontWeight: 'bold' }}
              onClick={() => setToasts((prev) => prev.filter((item) => item.id !== t.id))}
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};
