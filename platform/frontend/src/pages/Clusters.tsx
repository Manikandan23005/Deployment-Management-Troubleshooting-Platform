import React, { useState } from 'react';
import { 
  Server, Plus, RefreshCw, AlertTriangle, Star, 
  Zap, Upload, X, Trash2
} from 'lucide-react';
import { api } from '../services/api';
import { useCluster } from '../context/ClusterContext';
import { Loading } from '../components/Loading';

export const Clusters: React.FC = () => {
  const { clusters, activeCluster, refreshClusters, setActiveCluster, loading: contextLoading } = useCluster();
  const [loading, setLoading] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{ id: string; success: boolean; message: string } | null>(null);

  // Modal State
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [kubeconfigContent, setKubeconfigContent] = useState('');
  const [parsedContexts, setParsedContexts] = useState<any[]>([]);
  
  // Form State
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [environment, setEnvironment] = useState('Development');
  const [provider, setProvider] = useState('Minikube');
  const [selectedContext, setSelectedContext] = useState('');
  const [apiServer, setApiServer] = useState('');
  const [defaultNamespace, setDefaultNamespace] = useState('devops-nexus-prod');
  const [argocdUrl] = useState('');
  const [prometheusUrl] = useState('');
  const [lokiUrl] = useState('');
  const [isDefault, setIsDefault] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  const fetchClusters = async () => {
    setLoading(true);
    await refreshClusters();
    setLoading(false);
  };

  const handleTestConnection = async (clusterId: string) => {
    setTestingId(clusterId);
    setTestResult(null);
    try {
      const res = await api.testClusterConnection(clusterId);
      if (res.data && res.data.success) {
        const info = res.data.data;
        setTestResult({
          id: clusterId,
          success: info.connected,
          message: info.message
        });
      }
    } catch (e: any) {
      setTestResult({
        id: clusterId,
        success: false,
        message: e.response?.data?.detail || 'Connection test failed'
      });
    } finally {
      setTestingId(null);
    }
  };

  const handleSetDefault = async (clusterId: string) => {
    try {
      await api.setDefaultCluster(clusterId);
      await refreshClusters();
    } catch (e) {
      console.error('Failed to set default cluster:', e);
    }
  };

  const handleDeleteCluster = async (clusterId: string, name: string) => {
    if (window.confirm(`Are you sure you want to delete cluster "${name}" from the Multi-Cluster Registry?`)) {
      try {
        await api.deleteCluster(clusterId);
        await refreshClusters();
      } catch (e) {
        console.error('Failed to delete cluster:', e);
      }
    }
  };

  const handleKubeconfigUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = async (event) => {
        const text = event.target?.result as string;
        setKubeconfigContent(text);
        await parseKubeconfig(text);
      };
      reader.readAsText(file);
    }
  };

  const parseKubeconfig = async (content: string) => {
    try {
      const res = await api.parseKubeconfig(content);
      if (res.data && res.data.success && res.data.data.contexts) {
        const ctxs = res.data.data.contexts;
        setParsedContexts(ctxs);
        if (ctxs.length > 0) {
          const first = ctxs[0];
          setSelectedContext(first.context_name);
          setApiServer(first.api_server);
          if (first.context_name.includes('minikube')) {
            setProvider('Minikube');
            setName('Minikube Cluster');
          } else if (first.context_name.includes('kubernetes') || first.context_name.includes('admin')) {
            setProvider('kubeadm');
            setName('Kubeadm Production Cluster');
          }
        }
      }
    } catch (e) {
      console.error('Failed to parse kubeconfig:', e);
    }
  };

  const handleAddClusterSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setModalError(null);
    try {
      const payload = {
        name,
        description,
        environment,
        provider,
        context_name: selectedContext || 'default',
        kubeconfig_content: kubeconfigContent || null,
        api_server: apiServer || 'https://localhost:6443',
        authentication_type: 'Kubeconfig',
        default_namespace: defaultNamespace,
        is_default: isDefault,
        argocd_url: argocdUrl || null,
        prometheus_url: prometheusUrl || null,
        loki_url: lokiUrl || null
      };

      const res = await api.addCluster(payload);
      if (res.data && res.data.success) {
        setIsAddModalOpen(false);
        resetForm();
        await refreshClusters();
      }
    } catch (err: any) {
      setModalError(err.response?.data?.detail || 'Failed to add cluster to registry');
    } finally {
      setSubmitting(false);
    }
  };

  const resetForm = () => {
    setName('');
    setDescription('');
    setEnvironment('Development');
    setProvider('Minikube');
    setSelectedContext('');
    setApiServer('');
    setKubeconfigContent('');
    setParsedContexts([]);
    setIsDefault(false);
    setModalError(null);
  };

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-slate-900/80 border border-slate-800 p-6 rounded-2xl shadow-xl backdrop-blur-xl">
        <div className="space-y-1">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-blue-600/10 text-blue-400 border border-blue-500/20">
              <Server className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white tracking-wide">Multi-Cluster Registry</h1>
              <p className="text-xs text-slate-400">Enterprise multi-cluster management for Minikube, kubeadm, and Cloud Providers</p>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={fetchClusters}
            className="flex items-center space-x-2 px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition cursor-pointer"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="flex items-center space-x-2 px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-lg shadow-blue-500/20 transition cursor-pointer"
          >
            <Plus className="h-4 w-4" />
            <span>Add Cluster</span>
          </button>
        </div>
      </div>

      {/* Cluster Table */}
      {contextLoading ? (
        <Loading />
      ) : clusters.length === 0 ? (
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-12 text-center space-y-4 shadow-xl">
          <div className="w-16 h-16 rounded-full bg-blue-500/10 text-blue-400 flex items-center justify-center mx-auto border border-blue-500/20">
            <Server className="h-8 w-8" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white">No Kubernetes Clusters Registered</h3>
            <p className="text-sm text-slate-400 max-w-md mx-auto mt-1">
              Add a Kubernetes cluster using Kubeconfig or register an AWS Account to discover and manage Amazon EKS clusters.
            </p>
          </div>
          <div className="flex items-center justify-center gap-3 pt-2">
            <button
              onClick={() => setIsAddModalOpen(true)}
              className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold transition cursor-pointer shadow-lg shadow-blue-500/20"
            >
              <Plus className="h-4 w-4" />
              Add Kubernetes Cluster
            </button>
            <a
              href="/aws/accounts"
              className="inline-flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-xl text-xs font-semibold transition cursor-pointer"
            >
              Register AWS Account
            </a>
          </div>
        </div>
      ) : (
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/80 text-slate-400 uppercase tracking-wider font-semibold border-b border-slate-800">
                <tr>
                  <th className="px-6 py-4">Cluster Name</th>
                  <th className="px-6 py-4">Provider</th>
                  <th className="px-6 py-4">Environment</th>
                  <th className="px-6 py-4">Context / API Server</th>
                  <th className="px-6 py-4">Status</th>
                  <th className="px-6 py-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-200">
                {clusters.map((cluster) => {
                  const isActive = activeCluster?.id === cluster.id;
                  const isTesting = testingId === cluster.id;
                  const testRes = testResult?.id === cluster.id ? testResult : null;

                  return (
                    <tr key={cluster.id} className={`hover:bg-slate-800/40 transition ${isActive ? 'bg-blue-600/5' : ''}`}>
                      <td className="px-6 py-4">
                        <div className="flex items-center space-x-3">
                          <div className="p-2 rounded-lg bg-slate-800 border border-slate-700 text-blue-400">
                            <Server className="h-4 w-4" />
                          </div>
                          <div>
                            <div className="flex items-center space-x-2">
                              <span className="font-bold text-white text-sm">{cluster.name}</span>
                              {cluster.is_default && (
                                <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                                  <Star className="h-3 w-3 fill-amber-400" />
                                  <span>Default</span>
                                </span>
                              )}
                              {isActive && (
                                <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
                                  Active Context
                                </span>
                              )}
                            </div>
                            <p className="text-[11px] text-slate-400 font-mono mt-0.5">{cluster.id}</p>
                          </div>
                        </div>
                      </td>

                      <td className="px-6 py-4">
                        <span className={`inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-semibold border ${
                          cluster.provider === 'Minikube'
                            ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                            : cluster.provider === 'kubeadm'
                            ? 'bg-blue-500/10 text-blue-400 border-blue-500/20'
                            : 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20'
                        }`}>
                          {cluster.provider}
                        </span>
                      </td>

                      <td className="px-6 py-4">
                        <span className={`inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-semibold border ${
                          cluster.environment === 'Development'
                            ? 'bg-slate-800 text-slate-300 border-slate-700'
                            : cluster.environment === 'Production'
                            ? 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                            : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                        }`}>
                          {cluster.environment}
                        </span>
                      </td>

                      <td className="px-6 py-4 space-y-1 font-mono text-[11px]">
                        <p className="text-slate-200 font-semibold">{cluster.context_name}</p>
                        <p className="text-slate-500 truncate max-w-xs">{cluster.api_server || 'In-Cluster'}</p>
                      </td>

                      <td className="px-6 py-4">
                        <div className="space-y-1">
                          <span className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                            <span>{cluster.status}</span>
                          </span>
                          {testRes && (
                            <p className={`text-[10px] font-mono ${testRes.success ? 'text-emerald-400' : 'text-rose-400'}`}>
                              {testRes.message}
                            </p>
                          )}
                        </div>
                      </td>

                      <td className="px-6 py-4 text-right space-x-2">
                        <button
                          onClick={() => handleTestConnection(cluster.id)}
                          disabled={isTesting}
                          className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition cursor-pointer"
                        >
                          <Zap className={`h-3.5 w-3.5 inline mr-1 text-amber-400 ${isTesting ? 'animate-bounce' : ''}`} />
                          <span>{isTesting ? 'Testing...' : 'Test'}</span>
                        </button>
                        {!cluster.is_default && (
                          <button
                            onClick={() => handleSetDefault(cluster.id)}
                            className="px-3 py-1.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 text-xs font-semibold border border-amber-500/20 transition cursor-pointer"
                          >
                            <Star className="h-3.5 w-3.5 inline mr-1" />
                            <span>Set Default</span>
                          </button>
                        )}
                        {!isActive && (
                          <button
                            onClick={() => {
                              setActiveCluster(cluster);
                              window.location.reload();
                            }}
                            className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-md shadow-blue-500/20 transition cursor-pointer"
                          >
                            <span>Switch</span>
                          </button>
                        )}
                        {!cluster.is_default && (
                          <button
                            onClick={() => handleDeleteCluster(cluster.id, cluster.name)}
                            className="px-2 py-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 text-xs font-semibold border border-rose-500/20 transition cursor-pointer"
                            title="Delete cluster from registry"
                          >
                            <Trash2 className="h-3.5 w-3.5 inline" />
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Add Cluster Modal */}
      {isAddModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-xl w-full p-6 shadow-2xl space-y-6 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div className="flex items-center space-x-3">
                <div className="p-2 rounded-xl bg-blue-600/10 text-blue-400 border border-blue-500/20">
                  <Server className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-white">Add Kubernetes Cluster</h3>
                  <p className="text-xs text-slate-400">Import Minikube or kubeadm cluster via Kubeconfig</p>
                </div>
              </div>
              <button
                onClick={() => {
                  setIsAddModalOpen(false);
                  resetForm();
                }}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 cursor-pointer"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {modalError && (
              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center space-x-2">
                <AlertTriangle className="h-4 w-4 flex-shrink-0" />
                <span>{modalError}</span>
              </div>
            )}

            <form onSubmit={handleAddClusterSubmit} className="space-y-4 text-xs">
              {/* Kubeconfig Upload / Input */}
              <div className="space-y-2">
                <label className="block font-semibold text-slate-300">1. Kubeconfig Configuration</label>
                <div className="flex items-center gap-3">
                  <label className="flex items-center space-x-2 px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold border border-slate-700 cursor-pointer transition">
                    <Upload className="h-4 w-4 text-blue-400" />
                    <span>Upload .kube/config</span>
                    <input type="file" onChange={handleKubeconfigUpload} className="hidden" accept=".config,.yaml,.yml,text/*" />
                  </label>
                  <span className="text-slate-500">or paste content below</span>
                </div>
                <textarea
                  value={kubeconfigContent}
                  onChange={async (e) => {
                    setKubeconfigContent(e.target.value);
                    if (e.target.value.length > 20) {
                      await parseKubeconfig(e.target.value);
                    }
                  }}
                  rows={4}
                  placeholder="Paste contents of ~/.kube/config here..."
                  className="w-full p-3 rounded-xl bg-slate-950 border border-slate-800 text-slate-200 font-mono text-[11px] focus:outline-none focus:border-blue-500"
                />
              </div>

              {/* Context Selector */}
              {parsedContexts.length > 0 && (
                <div className="space-y-1">
                  <label className="block font-semibold text-slate-300">Target Context</label>
                  <select
                    value={selectedContext}
                    onChange={(e) => {
                      setSelectedContext(e.target.value);
                      const target = parsedContexts.find(c => c.context_name === e.target.value);
                      if (target) setApiServer(target.api_server);
                    }}
                    className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-slate-200 font-semibold focus:outline-none focus:border-blue-500"
                  >
                    {parsedContexts.map((ctx) => (
                      <option key={ctx.context_name} value={ctx.context_name}>
                        {ctx.context_name} ({ctx.api_server})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Metadata Form */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="block font-semibold text-slate-300">Cluster Display Name</label>
                  <input
                    type="text"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Kubeadm Prod Cluster"
                    className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-slate-200 focus:outline-none focus:border-blue-500"
                  />
                </div>

                <div className="space-y-1">
                  <label className="block font-semibold text-slate-300">Provider</label>
                  <select
                    value={provider}
                    onChange={(e) => setProvider(e.target.value)}
                    className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-slate-200 font-semibold focus:outline-none focus:border-blue-500"
                  >
                    <option value="Minikube">Minikube</option>
                    <option value="kubeadm">kubeadm</option>
                    <option value="EKS">AWS EKS</option>
                    <option value="GKE">Google GKE</option>
                    <option value="AKS">Azure AKS</option>
                    <option value="Custom">Custom Kubernetes</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="block font-semibold text-slate-300">Environment</label>
                  <select
                    value={environment}
                    onChange={(e) => setEnvironment(e.target.value)}
                    className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-slate-200 font-semibold focus:outline-none focus:border-blue-500"
                  >
                    <option value="Development">Development</option>
                    <option value="Staging">Staging</option>
                    <option value="Production">Production</option>
                    <option value="QA">QA</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="block font-semibold text-slate-300">API Server URL</label>
                  <input
                    type="text"
                    required
                    value={apiServer}
                    onChange={(e) => setApiServer(e.target.value)}
                    placeholder="https://192.168.49.2:8443"
                    className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-slate-200 font-mono text-[11px] focus:outline-none focus:border-blue-500"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="block font-semibold text-slate-300">Default Working Namespace</label>
                <input
                  type="text"
                  value={defaultNamespace}
                  onChange={(e) => setDefaultNamespace(e.target.value)}
                  className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-slate-200 font-mono text-[11px] focus:outline-none focus:border-blue-500"
                />
              </div>

              <div className="flex items-center space-x-2 pt-2">
                <input
                  type="checkbox"
                  id="is_default"
                  checked={isDefault}
                  onChange={(e) => setIsDefault(e.target.checked)}
                  className="h-4 w-4 rounded border-slate-700 bg-slate-950 text-blue-600 focus:ring-blue-500"
                />
                <label htmlFor="is_default" className="font-semibold text-slate-300 cursor-pointer">
                  Set as platform primary default cluster
                </label>
              </div>

              <div className="flex items-center justify-end space-x-3 border-t border-slate-800 pt-4">
                <button
                  type="button"
                  onClick={() => {
                    setIsAddModalOpen(false);
                    resetForm();
                  }}
                  className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold shadow-lg shadow-blue-500/20 cursor-pointer"
                >
                  {submitting ? 'Registering...' : 'Register Cluster'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
