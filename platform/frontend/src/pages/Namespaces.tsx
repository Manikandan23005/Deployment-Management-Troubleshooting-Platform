import React, { useEffect, useState } from 'react';
import { Table } from '../components/Table';
import { Loading } from '../components/Loading';
import { api } from '../services/api';
import { useScope } from '../context/ScopeContext';
import { Plus, Trash2, Layers } from 'lucide-react';
import { ActionConfirmationModal } from '../components/ActionConfirmationModal';

interface NamespaceItem {
  name: string;
  status: string;
  podsCount: number;
  cpuQuota: string;
  memoryQuota: string;
}

const Namespaces: React.FC = () => {
  const [namespaces, setNamespaces] = useState<NamespaceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedNs, setSelectedNs] = useState<NamespaceItem | null>(null);
  const [modalAction, setModalAction] = useState<'create' | 'delete' | null>(null);
  const [newNsName, setNewNsName] = useState('');
  const [actionLoading, setActionLoading] = useState(false);
  const { getScopeParams } = useScope();

  const userRole = localStorage.getItem('user_role') || 'Viewer';
  const canOperate = ['Administrator', 'Platform Engineer', 'DevOps Engineer'].includes(userRole);

  const fetchNamespaces = async () => {
    setLoading(true);
    try {
      const data = await api.getNamespaces(getScopeParams());
      setNamespaces(data || []);
    } catch (e) {
      console.warn("Failed to load namespaces:", e);
      setNamespaces([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNamespaces();
  }, [JSON.stringify(getScopeParams())]);

  const handleConfirmAction = async () => {
    if (!modalAction) return;
    setActionLoading(true);
    try {
      if (modalAction === 'delete' && selectedNs) {
        await api.deleteNamespace(selectedNs.name);
      } else if (modalAction === 'create' && newNsName) {
        await api.createNamespace(newNsName);
      }
      setSelectedNs(null);
      setModalAction(null);
      setNewNsName('');
      fetchNamespaces();
    } catch (e: any) {
      alert(e.message || 'Namespace operation failed due to RBAC policy.');
    } finally {
      setActionLoading(false);
    }
  };

  const columns = [
    { header: 'Namespace Name', accessor: (item: NamespaceItem) => <span className="font-bold text-slate-800 dark:text-white font-mono">{item.name}</span> },
    {
      header: 'Status',
      accessor: (item: NamespaceItem) => (
        <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
          {item.status}
        </span>
      )
    },
    { header: 'Running Pods', accessor: 'podsCount' as const },
    { header: 'CPU Quota Max', accessor: 'cpuQuota' as const },
    { header: 'Memory Quota Max', accessor: 'memoryQuota' as const },
    {
      header: 'Actions',
      accessor: (item: NamespaceItem) => (
        <div className="flex items-center justify-end">
          {canOperate && !['default', 'kube-system', 'monitoring'].includes(item.name) ? (
            <button
              onClick={() => { setSelectedNs(item); setModalAction('delete'); }}
              className="px-2.5 py-1 rounded-lg bg-rose-500/10 border border-rose-500/20 text-xs font-bold text-rose-400 hover:bg-rose-500/20 flex items-center gap-1 cursor-pointer"
            >
              <Trash2 className="h-3.5 w-3.5" />
              Delete
            </button>
          ) : (
            <span className="text-xs text-slate-500 italic">Protected System Scope</span>
          )}
        </div>
      )
    }
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-800 dark:text-white flex items-center gap-2">
            <Layers className="h-7 w-7 text-blue-500" />
            Kubernetes Cluster Namespaces
          </h2>
          <p className="text-xs text-slate-400 mt-1">Multi-tenant namespace isolation bounds and resource quotas.</p>
        </div>

        {canOperate && (
          <button
            onClick={() => {
              const val = prompt("Enter new Kubernetes Namespace name:");
              if (val) {
                setNewNsName(val);
                setSelectedNs(null);
                setModalAction('create');
              }
            }}
            className="px-4 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs shadow-lg shadow-blue-500/20 flex items-center gap-2 transition-all cursor-pointer"
          >
            <Plus className="h-4 w-4" />
            Create Namespace
          </button>
        )}
      </div>

      {loading ? <Loading /> : <Table columns={columns} data={namespaces} />}

      {/* Confirmation Modal */}
      {modalAction && (
        <ActionConfirmationModal
          isOpen={true}
          onClose={() => { setSelectedNs(null); setModalAction(null); }}
          onConfirm={handleConfirmAction}
          title={modalAction === 'create' ? 'Provision New Namespace' : 'Delete Namespace Scope'}
          description={modalAction === 'create'
            ? 'Specify the unique identifier for the new isolated Kubernetes namespace scope.'
            : `WARNING: You are about to delete namespace '${selectedNs?.name}'. All workloads inside will be terminated.`
          }
          resourceName={modalAction === 'create' ? (newNsName || 'new-namespace') : (selectedNs?.name || '')}
          resourceType="Namespace"
          actionType={modalAction === 'create' ? 'custom' : 'delete'}
          loading={actionLoading}
        />
      )}
    </div>
  );
};

export default Namespaces;
