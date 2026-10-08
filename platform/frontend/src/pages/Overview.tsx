import React, { useEffect, useState } from 'react';
import { Card } from '../components/Card';
import { Table } from '../components/Table';
import { Loading } from '../components/Loading';
import { api } from '../services/api';
import { AppInfo } from '../types';
import { Shield, Cpu, Layers, GitBranch, RefreshCw, GitCommit } from 'lucide-react';

import { useScope } from '../context/ScopeContext';
import { useCluster } from '../context/ClusterContext';

const Overview: React.FC = () => {
  const [apps, setApps] = useState<AppInfo[]>([]);
  const [metrics, setMetrics] = useState({ cpu_utilization: 0, memory_utilization: 0, disk_utilization: 0, network_throughput_bytes: 0 });
  const [gitDetails, setGitDetails] = useState({ owner: '', repository: '', branches: [] as string[], latest_commits: [] as any[] });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const { getScopeParams, getScopeLabel } = useScope();
  const { activeCluster, clusters, initialized } = useCluster();

  const isConnected = !!activeCluster && clusters.length > 0;

  const fetchDashboardData = async (silent = false) => {
    if (!silent) setLoading(true);
    else setRefreshing(true);
    
    try {
      const scopeParams = getScopeParams();
      
      const appsPromise = api.getApplications(scopeParams).catch(() => []);
      const metricsPromise = api.getClusterMetrics(scopeParams).catch(() => ({ cpu_utilization: 0, memory_utilization: 0, disk_utilization: 0, network_throughput_bytes: 0 }));
      const gitPromise = api.getGitHubDetails().catch(() => ({
        owner: 'Manikandan23005',
        repository: 'Deployment-Management-Troubleshooting-Platform',
        branches: ['main'],
        latest_commits: []
      }));

      const [appsData, metricsData, gitData] = await Promise.all([
        appsPromise,
        metricsPromise,
        gitPromise
      ]);

      setApps(appsData || []);
      setMetrics(metricsData || { cpu_utilization: 0, memory_utilization: 0, disk_utilization: 0, network_throughput_bytes: 0 });
      setGitDetails(gitData || { owner: 'Manikandan23005', repository: 'Deployment-Management-Troubleshooting-Platform', branches: ['main'], latest_commits: [] });
    } catch (e) {
      console.error("Dashboard fetch error:", e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    // Wait until ClusterContext has resolved the active cluster before the first
    // fetch, so a fresh page load behaves like a post-refresh load instead of
    // rendering a confident 0. Keep loading=true while not ready.
    if (!initialized) return;
    fetchDashboardData();
  }, [initialized, activeCluster?.id, isConnected, JSON.stringify(getScopeParams())]);

  // Real-time auto-refresh interval: 10 seconds (no-op until initialized)
  useEffect(() => {
    if (!initialized) return;
    const timer = setInterval(() => {
      fetchDashboardData(true);
    }, 10000);
    return () => clearInterval(timer);
  }, [initialized, activeCluster?.id, JSON.stringify(getScopeParams())]);

  const appColumns = [
    { header: 'Workload', accessor: 'name' as const },
    {
      header: 'Status',
      accessor: (item: AppInfo) => (
        <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${
          item.status === 'Synced' ? 'bg-emerald-500/10 text-emerald-500' :
          item.status === 'OutOfSync' ? 'bg-amber-500/10 text-amber-500' :
          item.status === 'Progressing' ? 'bg-blue-500/10 text-blue-500' :
          'bg-rose-500/10 text-rose-500'
        }`}>
          {item.status}
        </span>
      )
    },
    { header: 'Target Revision', accessor: 'targetRevision' as const },
    { header: 'Last Sync Action', accessor: 'lastSync' as const }
  ];

  if (loading) return <Loading />;

  return (
    <div className="space-y-8">
      {/* Dashboard Top Header & Namespace selector */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-800 dark:text-white">Unified Cluster Control</h1>
          <p className="text-sm text-slate-400 mt-1">Real-time telemetry streams from Prometheus, Loki and ArgoCD.</p>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          {refreshing && <RefreshCw className="h-4 w-4 text-blue-500 animate-spin" />}
          {activeCluster ? (
            <span className="px-3 py-1.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-500 dark:text-emerald-400 text-xs font-semibold flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>{activeCluster.name}</span>
              <span className="text-[10px] font-mono px-1 py-0.2 rounded bg-emerald-500/20">{activeCluster.provider}</span>
            </span>
          ) : (
            <span className="px-3 py-1.5 rounded-xl bg-slate-800 text-slate-400 text-xs font-semibold">
              Connecting Cluster...
            </span>
          )}
          <span className="px-3.5 py-1.5 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-500 text-xs font-bold">
            {getScopeLabel()}
          </span>
        </div>
      </div>

      {/* Cluster Aggregated Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card title="Deployments" value={`${apps.length} active`} subtext={`Filtered scope: ${getScopeLabel()}`} icon={GitBranch} />
        <Card title="CPU Utilization" value={`${metrics.cpu_utilization.toFixed(1)}%`} subtext="Cluster total capacity load" icon={Cpu} />
        <Card title="Memory Allocation" value={`${metrics.memory_utilization.toFixed(1)}%`} subtext="Memory capacity threshold" icon={Shield} />
        <Card title="Network Speed" value={`${(metrics.network_throughput_bytes / 1024).toFixed(1)} KB/s`} subtext="Active I/O ingress rates" icon={Layers} />
      </div>

      {/* Resource Utilization Gauges & Git Commit Viewer */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Resource Usage progress bars */}
        <div className="glass-panel p-6 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white/40 dark:bg-slate-900/40 space-y-6 lg:col-span-1">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-400">Resource Saturation</h2>
          
          <div className="space-y-4">
            <div className="space-y-1.5">
              <div className="flex justify-between text-xs font-semibold text-slate-500">
                <span>CPU Load</span>
                <span>{metrics.cpu_utilization.toFixed(1)}%</span>
              </div>
              <div className="h-2 w-full bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden">
                <div className="h-full bg-blue-500 rounded-full transition-all duration-500" style={{ width: `${metrics.cpu_utilization}%` }} />
              </div>
            </div>

            <div className="space-y-1.5">
              <div className="flex justify-between text-xs font-semibold text-slate-500">
                <span>Memory Allocation</span>
                <span>{metrics.memory_utilization.toFixed(1)}%</span>
              </div>
              <div className="h-2 w-full bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden">
                <div className="h-full bg-indigo-500 rounded-full transition-all duration-500" style={{ width: `${metrics.memory_utilization}%` }} />
              </div>
            </div>

            <div className="space-y-1.5">
              <div className="flex justify-between text-xs font-semibold text-slate-500">
                <span>Disk Storage capacity</span>
                <span>{metrics.disk_utilization.toFixed(1)}%</span>
              </div>
              <div className="h-2 w-full bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden">
                <div className="h-full bg-emerald-500 rounded-full transition-all duration-500" style={{ width: `${metrics.disk_utilization}%` }} />
              </div>
            </div>
          </div>
        </div>

        {/* Git Commit Viewer */}
        <div className="glass-panel p-6 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white/40 dark:bg-slate-900/40 space-y-4 lg:col-span-2">
          <div className="flex items-center gap-2">
            <GitCommit className="h-5 w-5 text-blue-500" />
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-400">Git Repository History ({gitDetails.repository})</h2>
          </div>

          <div className="divide-y divide-slate-200 dark:divide-slate-800">
            {gitDetails.latest_commits.length > 0 ? (
              gitDetails.latest_commits.map((commit: any, idx: number) => (
                <div key={idx} className="py-3.5 flex items-center justify-between gap-4">
                  <div className="space-y-0.5">
                    <p className="text-sm font-semibold text-slate-700 dark:text-slate-200 line-clamp-1">{commit.message}</p>
                    <p className="text-xs text-slate-400">Author: {commit.author}</p>
                  </div>
                  <span className="font-mono text-xs px-2.5 py-1 rounded-xl bg-slate-100 dark:bg-slate-800 text-blue-500">
                    {commit.sha}
                  </span>
                </div>
              ))
            ) : (
              <div className="py-8 text-center text-xs text-slate-400">
                No recent Git repository commits found.
              </div>
            )}
          </div>
        </div>

      </div>

      {/* Sync Status workloads table */}
      <div className="space-y-4">
        <h2 className="text-xl font-bold tracking-tight text-slate-800 dark:text-white">Active Workloads (GitOps Sync Status)</h2>
        <Table columns={appColumns} data={apps} />
      </div>

    </div>
  );
};

export default Overview;
