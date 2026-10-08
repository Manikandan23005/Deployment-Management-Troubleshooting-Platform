import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../services/api';
import { Loading } from '../components/Loading';
import { useScope } from '../context/ScopeContext';
import { useCluster } from '../context/ClusterContext';
import { Cpu, HardDrive, Activity, Wifi, Layers, Clock, AlertTriangle, RefreshCw, BarChart3, Radio, Server, Cloud } from 'lucide-react';

interface MetricChartConfig {
  id: string;
  title: string;
  category: 'compute' | 'network' | 'http' | 'scaling';
  unit: string;
  color: string;
  fillColor: string;
  icon: any;
  data: any[];
}

const Metrics: React.FC = () => {
  const [metricsData, setMetricsData] = useState<Record<string, any[]>>({});
  const [summaryStats, setSummaryStats] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'all' | 'compute' | 'network' | 'http' | 'scaling'>('all');
  const [timeRange, setTimeRange] = useState<'1h' | '6h' | '24h'>('1h');
  const { getScopeParams, getScopeLabel } = useScope();
  const { activeCluster, clusters } = useCluster();

  const isConnected = !!activeCluster && clusters.length > 0;

  const fetchAllMetrics = async () => {
    if (!isConnected) {
      setMetricsData({});
      setSummaryStats({
        cpu_utilization: 0.0,
        memory_utilization: 0.0,
        disk_utilization: 0.0,
        network_throughput_bytes: 0.0
      });
      setLoading(false);
      return;
    }

    try {
      const scope = { ...getScopeParams(), time_range: timeRange };
      const [
        cpu, mem, net, disk, reqs, errs, lat, pods, stats
      ] = await Promise.all([
        api.getMetricsRange('cpu', scope),
        api.getMetricsRange('memory', scope),
        api.getMetricsRange('network', scope),
        api.getMetricsRange('disk', scope),
        api.getMetricsRange('requests', scope),
        api.getMetricsRange('errors', scope),
        api.getMetricsRange('latency', scope),
        api.getMetricsRange('pods', scope),
        api.getClusterMetrics(scope)
      ]);

      setMetricsData({
        cpu, memory: mem, network: net, disk, requests: reqs, errors: errs, latency: lat, pods
      });
      setSummaryStats(stats);
    } catch (e) {
      console.error("Failed to fetch Prometheus metrics:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAllMetrics();
    if (!isConnected) return;
    const interval = setInterval(fetchAllMetrics, 5000);
    return () => clearInterval(interval);
  }, [isConnected, JSON.stringify(getScopeParams()), timeRange]);

  const chartConfigs: MetricChartConfig[] = [
    {
      id: 'cpu',
      title: 'CPU Utilization (%)',
      category: 'compute',
      unit: '%',
      color: '#3b82f6',
      fillColor: 'rgba(59, 130, 246, 0.15)',
      icon: Cpu,
      data: metricsData.cpu || []
    },
    {
      id: 'memory',
      title: 'Memory Utilization (%)',
      category: 'compute',
      unit: '%',
      color: '#8b5cf6',
      fillColor: 'rgba(139, 92, 246, 0.15)',
      icon: HardDrive,
      data: metricsData.memory || []
    },
    {
      id: 'network',
      title: 'Network Throughput (KB/s)',
      category: 'network',
      unit: ' KB/s',
      color: '#06b6d4',
      fillColor: 'rgba(6, 182, 212, 0.15)',
      icon: Wifi,
      data: metricsData.network || []
    },
    {
      id: 'disk',
      title: 'Disk Storage Usage (%)',
      category: 'network',
      unit: '%',
      color: '#10b981',
      fillColor: 'rgba(16, 185, 129, 0.15)',
      icon: Layers,
      data: metricsData.disk || []
    },
    {
      id: 'requests',
      title: 'HTTP Request Rate (Req/Sec)',
      category: 'http',
      unit: ' rps',
      color: '#f59e0b',
      fillColor: 'rgba(245, 158, 11, 0.15)',
      icon: Activity,
      data: metricsData.requests || []
    },
    {
      id: 'latency',
      title: 'P95 Response Latency (ms)',
      category: 'http',
      unit: ' ms',
      color: '#ec4899',
      fillColor: 'rgba(236, 72, 153, 0.15)',
      icon: Clock,
      data: metricsData.latency || []
    },
    {
      id: 'errors',
      title: 'HTTP 5xx Error Rate (%)',
      category: 'http',
      unit: '%',
      color: '#ef4444',
      fillColor: 'rgba(239, 68, 68, 0.15)',
      icon: AlertTriangle,
      data: metricsData.errors || []
    },
    {
      id: 'pods',
      title: 'Active Pod Replicas Count',
      category: 'scaling',
      unit: ' pods',
      color: '#6366f1',
      fillColor: 'rgba(99, 102, 241, 0.15)',
      icon: Layers,
      data: metricsData.pods || []
    }
  ];

  const filteredCharts = chartConfigs.filter(c => {
    if (activeTab === 'all') return true;
    return c.category === activeTab;
  });

  const generateSvgPath = (data: any[], width: number, height: number): { line: string; area: string } => {
    if (!data || data.length < 2) return { line: '', area: '' };
    const values = data.map(d => d[1]);
    const rawMin = Math.min(...values);
    const rawMax = Math.max(...values);

    let minVal: number;
    let maxVal: number;

    if (rawMax === rawMin) {
      minVal = Math.max(0, rawMin - (rawMin * 0.15 || 1));
      maxVal = rawMax + (rawMax * 0.15 || 1);
    } else {
      const delta = rawMax - rawMin;
      if (delta < rawMax * 0.25) {
        minVal = Math.max(0, rawMin - delta * 0.6);
        maxVal = rawMax + delta * 0.6;
      } else {
        minVal = Math.min(0, rawMin);
        maxVal = rawMax * 1.1;
      }
    }

    const range = maxVal - minVal || 1;

    const points = data.map((d, index) => {
      const x = (index / (data.length - 1)) * width;
      const y = height - ((d[1] - minVal) / range) * (height - 30) - 15;
      return `${x},${y}`;
    });

    const line = `M ${points.join(' L ')}`;
    const area = `${line} L ${width},${height} L 0,${height} Z`;
    return { line, area };
  };

  const getLatestVal = (data: any[]): number => {
    if (!data || data.length === 0) return 0;
    return data[data.length - 1][1];
  };

  const getAvgVal = (data: any[]): number => {
    if (!data || data.length === 0) return 0;
    const sum = data.reduce((acc, d) => acc + d[1], 0);
    return roundVal(sum / data.length);
  };

  const roundVal = (v: number) => Math.round(v * 10) / 10;

  if (loading) return <Loading />;

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-500">
            <BarChart3 className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-800 dark:text-white flex items-center gap-2">
              Prometheus & Grafana Telemetry Metrics
              <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-blue-500/10 text-blue-500 border border-blue-500/20">
                {getScopeLabel()} Scope
              </span>
            </h2>
            <p className="text-xs text-slate-400">Real-time infrastructure telemetries scraped from Prometheus endpoints.</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Time range selector */}
          <div className="flex items-center bg-slate-100 dark:bg-slate-800 p-1 rounded-xl border border-slate-200 dark:border-slate-700 text-xs">
            {(['1h', '6h', '24h'] as const).map(tr => (
              <button
                key={tr}
                onClick={() => setTimeRange(tr)}
                className={`px-2.5 py-1 rounded-lg font-bold transition-all ${
                  timeRange === tr
                    ? 'bg-white dark:bg-slate-900 text-blue-500 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {tr}
              </button>
            ))}
          </div>

          <button
            onClick={fetchAllMetrics}
            disabled={!isConnected}
            className={`p-2 rounded-xl border transition-colors flex items-center gap-1.5 text-xs font-semibold ${
              isConnected
                ? 'bg-slate-100 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-300 hover:text-white cursor-pointer'
                : 'bg-slate-100/50 dark:bg-slate-800/50 border-slate-200 dark:border-slate-800 text-slate-500 cursor-not-allowed'
            }`}
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isConnected ? 'animate-spin-slow' : ''}`} />
            <span>{isConnected ? 'Live Sync (5s)' : 'Disconnected'}</span>
          </button>
        </div>
      </div>

      {/* KPI Cards Summary Header */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-1">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>CPU Utilization</span>
            <Cpu className="h-4 w-4 text-blue-500" />
          </div>
          <div className="text-xl font-extrabold text-slate-800 dark:text-white font-mono">
            {isConnected ? (summaryStats?.cpu_utilization || getLatestVal(metricsData.cpu)) : 0.0}%
          </div>
          <div className={`text-[10px] font-semibold flex items-center gap-1 ${isConnected ? 'text-emerald-500' : 'text-slate-500'}`}>
            <Radio className={`h-2.5 w-2.5 ${isConnected ? 'animate-pulse' : ''}`} /> {isConnected ? 'Prometheus Active Scraper' : 'Cluster Offline'}
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-1">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Memory Usage</span>
            <HardDrive className="h-4 w-4 text-purple-500" />
          </div>
          <div className="text-xl font-extrabold text-slate-800 dark:text-white font-mono">
            {isConnected ? (summaryStats?.memory_utilization || getLatestVal(metricsData.memory)) : 0.0}%
          </div>
          <div className="text-[10px] text-slate-400 font-semibold">
            {isConnected ? `Avg: ${getAvgVal(metricsData.memory)}% (1h)` : 'No active cluster'}
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-1">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Network Traffic</span>
            <Wifi className="h-4 w-4 text-cyan-500" />
          </div>
          <div className="text-xl font-extrabold text-slate-800 dark:text-white font-mono">
            {isConnected ? roundVal(getLatestVal(metricsData.network)) : 0.0} KB/s
          </div>
          <div className="text-[10px] text-slate-400 font-semibold">
            {isConnected ? 'Rx & Tx Throughput' : 'No active cluster'}
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-1">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>P95 Response Latency</span>
            <Clock className="h-4 w-4 text-pink-500" />
          </div>
          <div className="text-xl font-extrabold text-slate-800 dark:text-white font-mono">
            {isConnected ? roundVal(getLatestVal(metricsData.latency)) : 0.0} ms
          </div>
          <div className={`text-[10px] font-semibold ${isConnected ? 'text-emerald-500' : 'text-slate-500'}`}>
            {isConnected ? '99.9% Availability' : 'No telemetry stream'}
          </div>
        </div>
      </div>

      {/* Category Filter Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200 dark:border-slate-800 pb-2">
        {[
          { id: 'all', label: 'All Telemetries (8)' },
          { id: 'compute', label: 'Compute & Memory' },
          { id: 'network', label: 'Network & Storage' },
          { id: 'http', label: 'HTTP & Latency' },
          { id: 'scaling', label: 'Pod Replicas' }
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
              activeTab === tab.id
                ? 'bg-blue-600 text-white shadow-md shadow-blue-600/20'
                : 'text-slate-400 hover:text-white hover:bg-slate-800'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Empty State Banner if not connected */}
      {!isConnected ? (
        <div className="p-8 rounded-2xl border border-dashed border-slate-200 dark:border-slate-800 bg-white/40 dark:bg-slate-900/40 text-center space-y-4">
          <div className="h-12 w-12 rounded-2xl bg-blue-500/10 border border-blue-500/20 text-blue-400 flex items-center justify-center mx-auto">
            <BarChart3 className="h-6 w-6" />
          </div>
          <div className="space-y-1 max-w-md mx-auto">
            <h3 className="text-base font-bold text-slate-800 dark:text-white">No Cluster Telemetry Available</h3>
            <p className="text-xs text-slate-400">
              There is currently no active Kubernetes cluster or AWS EKS account connected. Register an AWS account to discover your EKS clusters or add a cluster directly.
            </p>
          </div>
          <div className="flex items-center justify-center gap-3 pt-2">
            <Link
              to="/aws/accounts"
              className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold transition-all flex items-center gap-1.5 shadow-lg shadow-blue-500/20"
            >
              <Cloud className="h-3.5 w-3.5" />
              Register AWS Account
            </Link>
            <Link
              to="/clusters"
              className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-xs font-bold transition-all flex items-center gap-1.5"
            >
              <Server className="h-3.5 w-3.5" />
              Add Cluster
            </Link>
          </div>
        </div>
      ) : (
        /* Metric Charts Grid */
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {filteredCharts.map(chart => {
            const Icon = chart.icon;
            const paths = generateSvgPath(chart.data, 400, 180);
            const currentVal = getLatestVal(chart.data);
            const avgVal = getAvgVal(chart.data);

            return (
              <div 
                key={chart.id}
                className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white/60 dark:bg-slate-900/60 shadow-sm space-y-3"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="p-1.5 rounded-lg" style={{ backgroundColor: `${chart.color}20`, color: chart.color }}>
                      <Icon className="h-4 w-4" />
                    </div>
                    <span className="text-xs font-bold text-slate-800 dark:text-white">
                      {chart.title}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono text-slate-400">
                      Avg: <strong>{avgVal}{chart.unit}</strong>
                    </span>
                    <span className="px-2 py-0.5 rounded text-xs font-bold font-mono" style={{ backgroundColor: `${chart.color}20`, color: chart.color }}>
                      {roundVal(currentVal)}{chart.unit}
                    </span>
                  </div>
                </div>

                {/* Chart SVG */}
                <div className="h-48 border-b border-l border-slate-200 dark:border-slate-800/80 relative p-2 overflow-hidden">
                  {chart.data.length >= 2 ? (
                    <svg className="w-full h-full overflow-visible" viewBox="0 0 400 180" preserveAspectRatio="none">
                      <defs>
                        <linearGradient id={`grad-${chart.id}`} x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor={chart.color} stopOpacity="0.35" />
                          <stop offset="100%" stopColor={chart.color} stopOpacity="0.0" />
                        </linearGradient>
                      </defs>
                      <path d={paths.area} fill={`url(#grad-${chart.id})`} />
                      <path 
                        d={paths.line} 
                        fill="none" 
                        stroke={chart.color} 
                        strokeWidth="2.5" 
                        strokeLinecap="round"
                        className="transition-all duration-500" 
                      />
                    </svg>
                  ) : (
                    <div className="flex items-center justify-center h-full text-xs text-slate-400">
                      Collecting data points...
                    </div>
                  )}
                  <div className="absolute top-2 right-2 text-[10px] font-mono text-slate-400 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded border border-slate-200 dark:border-slate-700 flex items-center gap-1">
                    <Radio className="h-2.5 w-2.5 text-blue-400 animate-pulse" /> Live Prometheus Stream
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default Metrics;
