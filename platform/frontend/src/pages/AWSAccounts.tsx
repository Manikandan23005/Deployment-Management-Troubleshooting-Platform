import React, { useState, useEffect } from 'react';
import { 
  Cloud, Plus, RefreshCw, CheckCircle2, XCircle, AlertTriangle, 
  Trash2, ShieldCheck, Server, ArrowRight,
  Lock, Globe, Info, ChevronDown, ChevronRight
} from 'lucide-react';
import { api } from '../services/api';
import { Loading } from '../components/Loading';
import { useCluster } from '../context/ClusterContext';

interface AWSAccount {
  id: string;
  name: string;
  account_id: string;
  role_arn: string;
  default_region: string;
  status: string;
  created_at: string;
  updated_at: string;
  last_validated_at?: string;
}

interface EKSCluster {
  name: string;
  arn: string;
  status: string;
  version?: string;
  endpoint?: string;
  region: string;
  account_id: string;
  certificate_authority_available: boolean;
  platform_version?: string;
}

interface TestResult {
  account_id: string;
  success: boolean;
  status: string;
  message: string;
  assumed_role_arn?: string;
  region?: string;
  timestamp?: string;
}

export const AWSAccountsPage: React.FC = () => {
  const [accounts, setAccounts] = useState<AWSAccount[]>([]);
  const [loading, setLoading] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, TestResult>>({});
  
  // Cluster discovery state
  const [discoveringId, setDiscoveringId] = useState<string | null>(null);
  const [clustersByAccount, setClustersByAccount] = useState<Record<string, EKSCluster[]>>({});
  const [expandedAccountIds, setExpandedAccountIds] = useState<Record<string, boolean>>({});
  const [registeringCluster, setRegisteringCluster] = useState<string | null>(null);
  const [registeredTargetSuccess, setRegisteredTargetSuccess] = useState<string | null>(null);

  // Modal State
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [accountName, setAccountName] = useState('');
  const [awsAccountId, setAwsAccountId] = useState('');
  const [roleArn, setRoleArn] = useState('');
  const [defaultRegion, setDefaultRegion] = useState('us-east-1');
  const [submitting, setSubmitting] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  const fetchAccounts = async () => {
    setLoading(true);
    try {
      const res = await api.getAWSAccounts();
      if (res.data && res.data.success) {
        setAccounts(res.data.data);
      }
    } catch (e: any) {
      console.error('Failed to fetch AWS accounts:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAccounts();
  }, []);

  const handleTestConnection = async (accountId: string) => {
    setTestingId(accountId);
    try {
      const res = await api.testAWSAccountConnection(accountId);
      if (res.data && res.data.success) {
        const data = res.data.data;
        setTestResults(prev => ({
          ...prev,
          [accountId]: {
            account_id: data.account_id,
            success: data.success,
            status: data.status,
            message: data.message,
            assumed_role_arn: data.assumed_role_arn,
            region: data.region,
            timestamp: data.timestamp
          }
        }));
        // Refresh account list to show updated status
        fetchAccounts();
      }
    } catch (e: any) {
      setTestResults(prev => ({
        ...prev,
        [accountId]: {
          account_id: accountId,
          success: false,
          status: 'FAILED',
          message: e.response?.data?.detail || e.message || 'Connection test failed'
        }
      }));
    } finally {
      setTestingId(null);
    }
  };

  const { refreshClusters } = useCluster();

  const handleDiscoverClusters = async (account: AWSAccount) => {
    setDiscoveringId(account.id);
    setExpandedAccountIds(prev => ({ ...prev, [account.id]: true }));
    try {
      const res = await api.discoverEKSClusters(account.id, account.default_region);
      if (res.data && res.data.success) {
        const rawClusters = Array.isArray(res.data.data) 
          ? res.data.data 
          : (res.data.data?.clusters || []);
        setClustersByAccount(prev => ({
          ...prev,
          [account.id]: rawClusters
        }));
      }
    } catch (e: any) {
      console.error('Failed to discover EKS clusters:', e);
      alert(`EKS Discovery Failed: ${e.response?.data?.detail || e.message}`);
    } finally {
      setDiscoveringId(null);
    }
  };

  const handleRegisterEKSTarget = async (account: AWSAccount, clusterName: string) => {
    setRegisteringCluster(`${account.id}-${clusterName}`);
    setRegisteredTargetSuccess(null);
    try {
      const res = await api.registerEKSClusterTarget(account.id, clusterName);
      if (res.data && res.data.success) {
        setRegisteredTargetSuccess(`Cluster "${clusterName}" registered as target in Multi-Cluster Registry!`);
        await refreshClusters();
        setTimeout(() => setRegisteredTargetSuccess(null), 5000);
      }
    } catch (e: any) {
      alert(`Failed to register EKS target: ${e.response?.data?.detail || e.message}`);
    } finally {
      setRegisteringCluster(null);
    }
  };

  const handleDeleteAccount = async (account: AWSAccount) => {
    if (window.confirm(`Are you sure you want to remove registered AWS Account "${account.name}" (${account.account_id})?`)) {
      try {
        await api.deleteAWSAccount(account.id);
        fetchAccounts();
      } catch (e: any) {
        alert(`Failed to delete account: ${e.response?.data?.detail || e.message}`);
      }
    }
  };

  const handleCreateAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    setModalError(null);

    // Validation
    const cleanAccountId = awsAccountId.trim();
    if (!/^\d{12}$/.test(cleanAccountId)) {
      setModalError('AWS Account ID must be exactly 12 numeric digits.');
      return;
    }

    const cleanRoleArn = roleArn.trim();
    if (!cleanRoleArn.startsWith('arn:aws:iam::') || !cleanRoleArn.includes(':role/')) {
      setModalError('Target Role ARN must match format: arn:aws:iam::<account-id>:role/<role-name>');
      return;
    }

    setSubmitting(true);
    try {
      const res = await api.registerAWSAccount({
        name: accountName.trim(),
        account_id: cleanAccountId,
        role_arn: cleanRoleArn,
        default_region: defaultRegion
      });

      if (res.data && res.data.success) {
        setIsAddModalOpen(false);
        setAccountName('');
        setAwsAccountId('');
        setRoleArn('');
        fetchAccounts();
      }
    } catch (e: any) {
      setModalError(e.response?.data?.detail || e.message || 'Registration failed');
    } finally {
      setSubmitting(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'CONNECTED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="h-3.5 w-3.5" />
            Connected
          </span>
        );
      case 'VALIDATING':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
            <RefreshCw className="h-3.5 w-3.5 animate-spin" />
            Validating
          </span>
        );
      case 'FAILED':
      case 'ACCESS_DENIED':
      case 'ROLE_NOT_FOUND':
      case 'ACCOUNT_MISMATCH':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20">
            <XCircle className="h-3.5 w-3.5" />
            {status}
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-500/10 text-slate-600 dark:text-slate-400 border border-slate-500/20">
            <Info className="h-3.5 w-3.5" />
            Registered
          </span>
        );
    }
  };

  const toggleExpand = (accountId: string) => {
    setExpandedAccountIds(prev => ({ ...prev, [accountId]: !prev[accountId] }));
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-blue-600/10 rounded-xl text-blue-600 dark:text-blue-400">
              <Cloud className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
                AWS Accounts & Amazon EKS Integration
              </h1>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Secure cross-account access via STS AssumeRole. Zero static credentials stored.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 w-full sm:w-auto">
          <button
            onClick={fetchAccounts}
            className="p-2.5 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 transition-colors"
            title="Refresh accounts"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-semibold shadow-lg shadow-blue-500/20 transition-all"
          >
            <Plus className="h-4 w-4" />
            Register AWS Account
          </button>
        </div>
      </div>

      {/* Target Registration Success Banner */}
      {registeredTargetSuccess && (
        <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-sm flex items-center gap-2">
          <CheckCircle2 className="h-5 w-5 flex-shrink-0" />
          <span>{registeredTargetSuccess}</span>
        </div>
      )}

      {/* Quick Security Architecture Banner */}
      <div className="p-4 rounded-xl bg-indigo-500/5 border border-indigo-500/20 flex items-center justify-between text-xs text-indigo-700 dark:text-indigo-300">
        <div className="flex items-center gap-3">
          <ShieldCheck className="h-5 w-5 text-indigo-500 flex-shrink-0" />
          <span>
            <strong>Zero Long-Lived Credentials:</strong> DevOps Nexus authenticates directly using AWS STS AssumeRole temporary session tokens. Kubernetes API authentication against EKS uses ephemeral presigned tokens (<code className="font-mono text-[11px] bg-indigo-500/10 px-1 py-0.5 rounded">k8s-aws-v1.</code>).
          </span>
        </div>
      </div>

      {/* Accounts List */}
      {loading && accounts.length === 0 ? (
        <Loading />
      ) : accounts.length === 0 ? (
        <div className="bg-white dark:bg-slate-900 p-12 rounded-2xl border border-slate-200 dark:border-slate-800 text-center space-y-4">
          <div className="w-16 h-16 rounded-full bg-blue-500/10 text-blue-500 flex items-center justify-center mx-auto">
            <Cloud className="h-8 w-8" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-slate-800 dark:text-white">No AWS Accounts Registered</h3>
            <p className="text-sm text-slate-500 dark:text-slate-400 max-w-md mx-auto mt-1">
              Register an AWS Account with an IAM Role ARN to enable autonomous EKS cluster discovery, telemetry inspection, and verified remediation.
            </p>
          </div>
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-semibold transition-all shadow-md shadow-blue-500/10"
          >
            <Plus className="h-4 w-4" />
            Register Your First AWS Account
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {accounts.map((account) => {
            const isExpanded = !!expandedAccountIds[account.id];
            const testResult = testResults[account.id];
            const discoveredClusters = clustersByAccount[account.id] || [];
            const isDiscovering = discoveringId === account.id;

            return (
              <div 
                key={account.id}
                className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden shadow-sm transition-all"
              >
                {/* Account Main Card */}
                <div className="p-6">
                  <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                    {/* Left: Account Identity */}
                    <div className="space-y-1.5">
                      <div className="flex items-center gap-3 flex-wrap">
                        <button
                          onClick={() => toggleExpand(account.id)}
                          className="text-slate-400 hover:text-slate-200 transition-colors p-1"
                        >
                          {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                        </button>
                        <h2 className="text-lg font-bold text-slate-900 dark:text-white">
                          {account.name}
                        </h2>
                        {getStatusBadge(account.status)}
                      </div>
                      
                      <div className="flex items-center gap-4 text-xs text-slate-500 dark:text-slate-400 flex-wrap pl-7">
                        <span className="flex items-center gap-1 font-mono">
                          <strong className="text-slate-700 dark:text-slate-300">Account ID:</strong> {account.account_id}
                        </span>
                        <span className="flex items-center gap-1">
                          <Globe className="h-3 w-3 text-slate-400" />
                          <strong className="text-slate-700 dark:text-slate-300">Region:</strong> {account.default_region}
                        </span>
                        <span className="flex items-center gap-1 font-mono truncate max-w-md" title={account.role_arn}>
                          <Lock className="h-3 w-3 text-slate-400" />
                          <strong className="text-slate-700 dark:text-slate-300">Role:</strong> {account.role_arn}
                        </span>
                      </div>
                    </div>

                    {/* Right: Actions */}
                    <div className="flex items-center gap-2.5 flex-wrap pl-7 lg:pl-0">
                      <button
                        onClick={() => handleTestConnection(account.id)}
                        disabled={testingId === account.id}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200 transition-all disabled:opacity-50"
                      >
                        <RefreshCw className={`h-3.5 w-3.5 ${testingId === account.id ? 'animate-spin text-blue-500' : ''}`} />
                        {testingId === account.id ? 'Testing STS...' : 'Test STS Connection'}
                      </button>

                      <button
                        onClick={() => handleDiscoverClusters(account)}
                        disabled={isDiscovering}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-xl bg-blue-50 dark:bg-blue-900/30 hover:bg-blue-100 dark:hover:bg-blue-800/40 border border-blue-200 dark:border-blue-700/50 text-blue-600 dark:text-blue-300 transition-all disabled:opacity-50"
                      >
                        <Server className={`h-3.5 w-3.5 ${isDiscovering ? 'animate-spin' : ''}`} />
                        {isDiscovering ? 'Discovering EKS...' : 'Discover EKS Clusters'}
                      </button>

                      <button
                        onClick={() => handleDeleteAccount(account)}
                        className="p-1.5 text-slate-400 hover:text-rose-500 hover:bg-rose-500/10 rounded-lg transition-colors"
                        title="Remove AWS Account"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>

                  {/* Test Connection Banner if available */}
                  {testResult && (
                    <div className={`mt-4 p-3.5 rounded-xl text-xs flex items-start gap-2.5 ${
                      testResult.success 
                        ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-700 dark:text-emerald-300' 
                        : 'bg-rose-500/10 border border-rose-500/20 text-rose-700 dark:text-rose-300'
                    }`}>
                      {testResult.success ? (
                        <CheckCircle2 className="h-4 w-4 text-emerald-500 flex-shrink-0 mt-0.5" />
                      ) : (
                        <AlertTriangle className="h-4 w-4 text-rose-500 flex-shrink-0 mt-0.5" />
                      )}
                      <div className="space-y-0.5">
                        <div className="font-bold">{testResult.message}</div>
                        {testResult.assumed_role_arn && (
                          <div className="font-mono text-[11px] opacity-90">
                            Assumed Identity: {testResult.assumed_role_arn}
                          </div>
                        )}
                        {testResult.timestamp && (
                          <div className="text-[10px] opacity-75">
                            Validated at: {new Date(testResult.timestamp).toLocaleString()}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>

                {/* Collapsible EKS Clusters List */}
                {isExpanded && (
                  <div className="border-t border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 p-6 space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Server className="h-4 w-4 text-blue-500" />
                        <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200">
                          Discovered Amazon EKS Clusters ({discoveredClusters.length})
                        </h4>
                      </div>
                      
                      {discoveredClusters.length > 0 && (
                        <span className="text-xs text-slate-500 dark:text-slate-400">
                          Region: {account.default_region}
                        </span>
                      )}
                    </div>

                    {isDiscovering ? (
                      <div className="p-8 text-center text-xs text-slate-500 flex items-center justify-center gap-2">
                        <RefreshCw className="h-4 w-4 animate-spin text-blue-500" />
                        <span>Querying AWS EKS APIs via assumed role...</span>
                      </div>
                    ) : discoveredClusters.length === 0 ? (
                      <div className="p-6 text-center text-xs text-slate-500 dark:text-slate-400 bg-white dark:bg-slate-800/50 rounded-xl border border-dashed border-slate-300 dark:border-slate-700">
                        No EKS clusters discovered in region <strong>{account.default_region}</strong> yet. Click "Discover EKS Clusters" to scan this account.
                      </div>
                    ) : (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {discoveredClusters.map((cluster) => {
                          const isReg = registeringCluster === `${account.id}-${cluster.name}`;
                          return (
                            <div 
                              key={cluster.name}
                              className="p-4 rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700/80 shadow-sm space-y-3"
                            >
                              <div className="flex items-start justify-between gap-2">
                                <div>
                                  <h5 className="font-bold text-sm text-slate-900 dark:text-white flex items-center gap-1.5">
                                    {cluster.name}
                                  </h5>
                                  <div className="text-[11px] text-slate-500 font-mono truncate max-w-xs" title={cluster.arn}>
                                    {cluster.arn}
                                  </div>
                                </div>
                                <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                  cluster.status === 'ACTIVE' 
                                    ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20' 
                                    : 'bg-amber-500/10 text-amber-500 border border-amber-500/20'
                                }`}>
                                  {cluster.status}
                                </span>
                              </div>

                              <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-600 dark:text-slate-300 bg-slate-50 dark:bg-slate-900/50 p-2.5 rounded-lg">
                                <div>
                                  <span className="text-slate-400">K8s Version:</span>{' '}
                                  <strong className="font-mono">{cluster.version || '1.29'}</strong>
                                </div>
                                <div>
                                  <span className="text-slate-400">Platform:</span>{' '}
                                  <strong className="font-mono">{cluster.platform_version || 'eks.1'}</strong>
                                </div>
                                <div>
                                  <span className="text-slate-400">Region:</span>{' '}
                                  <strong>{cluster.region}</strong>
                                </div>
                                <div>
                                  <span className="text-slate-400">CA Cert:</span>{' '}
                                  <strong className={cluster.certificate_authority_available ? 'text-emerald-500' : 'text-amber-500'}>
                                    {cluster.certificate_authority_available ? 'Available' : 'Missing'}
                                  </strong>
                                </div>
                              </div>

                              <div className="flex items-center justify-between pt-1">
                                <span className="text-[10px] text-slate-400">
                                  Uses short-lived STS bearer token
                                </span>
                                
                                <button
                                  onClick={() => handleRegisterEKSTarget(account, cluster.name)}
                                  disabled={isReg || cluster.status !== 'ACTIVE'}
                                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold shadow-sm transition-all disabled:opacity-50"
                                >
                                  {isReg ? (
                                    <RefreshCw className="h-3 w-3 animate-spin" />
                                  ) : (
                                    <ArrowRight className="h-3 w-3" />
                                  )}
                                  {isReg ? 'Registering...' : 'Register as Target'}
                                </button>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Register AWS Account Modal */}
      {isAddModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl w-full max-w-lg overflow-hidden shadow-2xl animate-in fade-in zoom-in-95 duration-200">
            <div className="p-6 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="p-2 bg-blue-500/10 rounded-xl text-blue-600 dark:text-blue-400">
                  <Cloud className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                    Register AWS Account
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Connect via cross-account IAM Role ARN
                  </p>
                </div>
              </div>
              <button 
                onClick={() => setIsAddModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateAccount} className="p-6 space-y-4">
              {modalError && (
                <div className="p-3 bg-rose-500/10 border border-rose-500/20 text-rose-600 dark:text-rose-400 text-xs rounded-xl flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 flex-shrink-0" />
                  <span>{modalError}</span>
                </div>
              )}

              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
                  Account Friendly Name
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Production AWS, Staging Account"
                  value={accountName}
                  onChange={(e) => setAccountName(e.target.value)}
                  className="w-full px-3.5 py-2.5 bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-xl text-sm text-slate-900 dark:text-white focus:outline-none focus:border-blue-500 transition-colors"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
                    AWS Account ID (12 digits)
                  </label>
                  <input
                    type="text"
                    required
                    maxLength={12}
                    placeholder="123456789012"
                    value={awsAccountId}
                    onChange={(e) => setAwsAccountId(e.target.value.replace(/\D/g, ''))}
                    className="w-full px-3.5 py-2.5 font-mono bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-xl text-sm text-slate-900 dark:text-white focus:outline-none focus:border-blue-500 transition-colors"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
                    Default Region
                  </label>
                  <select
                    value={defaultRegion}
                    onChange={(e) => setDefaultRegion(e.target.value)}
                    className="w-full px-3.5 py-2.5 bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-xl text-sm text-slate-900 dark:text-white focus:outline-none focus:border-blue-500 transition-colors cursor-pointer"
                  >
                    <option value="us-east-1">us-east-1 (N. Virginia)</option>
                    <option value="us-west-2">us-west-2 (Oregon)</option>
                    <option value="eu-west-1">eu-west-1 (Ireland)</option>
                    <option value="eu-central-1">eu-central-1 (Frankfurt)</option>
                    <option value="ap-south-1">ap-south-1 (Mumbai)</option>
                    <option value="ap-southeast-1">ap-southeast-1 (Singapore)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
                  Target IAM Role ARN
                </label>
                <input
                  type="text"
                  required
                  placeholder="arn:aws:iam::123456789012:role/DevOpsNexusAccessRole"
                  value={roleArn}
                  onChange={(e) => setRoleArn(e.target.value)}
                  className="w-full px-3.5 py-2.5 font-mono bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-xl text-sm text-slate-900 dark:text-white focus:outline-none focus:border-blue-500 transition-colors"
                />
                <p className="text-[11px] text-slate-400 mt-1">
                  The IAM Role must have a Trust Relationship allowing DevOps Nexus to assume it.
                </p>
              </div>

              {/* Security Callout */}
              <div className="p-3.5 rounded-xl bg-slate-100 dark:bg-slate-800 text-[11px] text-slate-600 dark:text-slate-300 space-y-1">
                <div className="font-bold flex items-center gap-1 text-slate-800 dark:text-slate-200">
                  <ShieldCheck className="h-3.5 w-3.5 text-blue-500" />
                  Security Guarantee
                </div>
                <div>
                  DevOps Nexus never prompts for or stores AWS Secret Access Keys. All operations use short-lived STS tokens discarded upon expiry.
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-sm font-semibold text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-semibold shadow-lg shadow-blue-500/20 transition-all disabled:opacity-50 flex items-center gap-2"
                >
                  {submitting && <RefreshCw className="h-4 w-4 animate-spin" />}
                  Register Account
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default AWSAccountsPage;
