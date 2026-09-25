import React, { useEffect, useState } from 'react';
import { Table } from '../components/Table';
import { Loading } from '../components/Loading';
import { api } from '../services/api';
import { NodeInfo } from '../types';
import { Server, Plus, RefreshCw } from 'lucide-react';

const Nodes: React.FC = () => {
  const [nodes, setNodes] = useState<NodeInfo[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchNodes = async () => {
    setLoading(true);
    try {
      const data = await api.getNodes();
      setNodes(data || []);
    } catch (e) {
      console.warn("Failed to fetch nodes:", e);
      setNodes([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNodes();
  }, []);

  const columns = [
    { header: 'Node Name', accessor: 'name' as const },
    {
      header: 'Status',
      accessor: (item: NodeInfo) => (
        <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
          item.status === 'Ready' ? 'bg-emerald-500/10 text-emerald-500' : 'bg-rose-500/10 text-rose-500'
        }`}>
          {item.status}
        </span>
      )
    },
    { header: 'Role', accessor: 'role' as const },
    { header: 'CPU Allocation', accessor: 'cpuAllocated' as const },
    { header: 'Memory Allocation', accessor: 'memoryAllocated' as const },
    { header: 'Internal IP', accessor: 'ipAddress' as const }
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-800 dark:text-white">Cluster Worker Nodes</h2>
          <p className="text-xs text-slate-400 mt-1">Live physical and cloud worker node instances.</p>
        </div>
        <button
          onClick={fetchNodes}
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-semibold transition cursor-pointer"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {loading ? (
        <Loading />
      ) : nodes.length === 0 ? (
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-12 text-center space-y-4 shadow-xl">
          <div className="w-16 h-16 rounded-full bg-blue-500/10 text-blue-400 flex items-center justify-center mx-auto border border-blue-500/20">
            <Server className="h-8 w-8" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white">No Worker Nodes Found</h3>
            <p className="text-sm text-slate-400 max-w-md mx-auto mt-1">
              No active Kubernetes cluster connection detected. Register an AWS Account to discover Amazon EKS nodes or connect a local cluster.
            </p>
          </div>
          <div className="flex items-center justify-center gap-3 pt-2">
            <a
              href="/clusters"
              className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold transition cursor-pointer shadow-lg shadow-blue-500/20"
            >
              <Plus className="h-4 w-4" />
              Add Cluster
            </a>
            <a
              href="/aws/accounts"
              className="inline-flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-xl text-xs font-semibold transition cursor-pointer"
            >
              Register AWS Account
            </a>
          </div>
        </div>
      ) : (
        <Table columns={columns} data={nodes} emptyMessage="No nodes found." />
      )}
    </div>
  );
};

export default Nodes;
