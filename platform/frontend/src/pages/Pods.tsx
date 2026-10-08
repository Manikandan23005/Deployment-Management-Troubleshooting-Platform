import React, { useEffect, useState } from 'react';
import { EnterpriseTable, ColumnDef } from '../components/EnterpriseTable';
import { SkeletonLoader } from '../components/SkeletonLoader';
import { EnterpriseEmptyState } from '../components/EnterpriseEmptyState';
import { api } from '../services/api';
import { useScope } from '../context/ScopeContext';
import { useCluster } from '../context/ClusterContext';
import { ActionConfirmationModal } from '../components/ActionConfirmationModal';
import { TemporaryDeletePodModal } from '../components/TemporaryDeletePodModal';
import { RefreshCw, Trash2, FileText, ExternalLink, Box, GitBranch, CheckCircle2, AlertTriangle, XCircle } from 'lucide-react';
import { colors } from '../theme/designTokens';

interface PodItem {
  name: string;
  podName?: string;
  namespace: string;
  status: string;
  restarts: number;
  gitopsManaged: boolean;
  deploymentName?: string;
  applicationName?: string;
  ownerKind?: string;
  ownerName?: string;
  manager?: string;
}

const Pods: React.FC = () => {
  const [pods, setPods] = useState<PodItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedPod, setSelectedPod] = useState<PodItem | null>(null);
  const [modalAction, setModalAction] = useState<'restart' | 'delete' | null>(null);
  const [tempDeletePodTarget, setTempDeletePodTarget] = useState<PodItem | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const { getScopeParams } = useScope();
  const { activeCluster } = useCluster();

  const userRole = localStorage.getItem('user_role') || 'Viewer';
  const canOperate = ['Administrator', 'Platform Engineer', 'DevOps Engineer'].includes(userRole);

  const loadPods = async () => {
    setLoading(true);
    try {
      const data = await api.getPods(undefined, getScopeParams());
      setPods(data || []);
    } catch (e) {
      console.warn("Failed to load pods:", e);
      setPods([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPods();
  }, [activeCluster?.id, JSON.stringify(getScopeParams())]);

  const handleConfirmAction = async () => {
    if (!selectedPod || !modalAction) return;
    setActionLoading(true);
    try {
      if (modalAction === 'restart') {
        await api.restartPod(selectedPod.namespace, selectedPod.name);
      } else if (modalAction === 'delete') {
        await api.deletePod(selectedPod.namespace, selectedPod.name);
      }
      setSelectedPod(null);
      setModalAction(null);
      loadPods();
    } catch (e: any) {
      alert(e.message || 'Operation failed due to RBAC policy or cluster exception.');
    } finally {
      setActionLoading(false);
    }
  };

  // --- Derived KPI Stats ---
  const totalPods = pods.length;
  const runningCount = pods.filter(p => p.status === 'Running').length;
  const pendingCount = pods.filter(p => p.status === 'Pending').length;
  const crashCount = pods.filter(p => p.status !== 'Running' && p.status !== 'Pending').length;

  // --- EnterpriseTable Column Definitions ---
  const columns: ColumnDef<PodItem>[] = [
    {
      key: 'name',
      header: 'Pod Name',
      sortable: true,
      render: (item) => (
        <div className="space-y-1" data-ai-resource data-ai-name={item.name} data-ai-kind="pod" data-ai-namespace={item.namespace}>
          <div className="font-bold text-white text-sm flex items-center gap-2 cursor-context-menu" title="Right-click for AI Actions" style={{ fontFamily: "'Fira Code', monospace" }}>
            <Box className="h-4 w-4" style={{ color: colors.semantic.info.text }} />
            <span className="truncate max-w-[280px]">{item.name}</span>
          </div>
          <div className="text-[11px] font-mono flex items-center gap-3" style={{ color: colors.slate[400] }}>
            <span>Namespace: <strong style={{ color: colors.semantic.info.text }}>{item.namespace}</strong></span>
            {item.ownerKind && <span>Owner: <strong style={{ color: colors.slate[300] }}>{item.ownerKind}</strong></span>}
          </div>
        </div>
      )
    },
    {
      key: 'gitopsManaged',
      header: 'Management',
      render: (item) => (
        <div className="space-y-1.5">
          {item.gitopsManaged ? (
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold group relative cursor-pointer" style={{
              background: colors.semantic.success.bg,
              color: colors.semantic.success.text,
              border: `1px solid ${colors.semantic.success.border}`,
            }}>
              <span className="h-2 w-2 rounded-full animate-pulse" style={{ background: colors.semantic.success.badgeBg }} />
              GitOps Managed

              {/* Tooltip Card */}
              <div className="hidden group-hover:block absolute top-full left-0 mt-2 z-40 w-64 p-3 rounded-xl shadow-2xl space-y-1.5 text-[11px]" style={{
                background: colors.slate[900],
                border: `1px solid ${colors.slate[800]}`,
                color: colors.slate[300],
              }}>
                <div className="flex items-center justify-between pb-1.5 font-bold text-white" style={{ borderBottom: `1px solid ${colors.slate[800]}` }}>
                  <span>GitOps Ownership</span>
                  <span className="text-[10px] font-mono" style={{ color: colors.semantic.success.text }}>ArgoCD</span>
                </div>
                <div><span style={{ color: colors.slate[500] }}>Deployment:</span> <strong className="text-white">{item.deploymentName || 'N/A'}</strong></div>
                <div><span style={{ color: colors.slate[500] }}>Application:</span> <strong style={{ color: colors.semantic.warning.text }}>{item.applicationName || 'N/A'}</strong></div>
                <div><span style={{ color: colors.slate[500] }}>Parent:</span> <span className="font-mono" style={{ color: colors.slate[300] }}>{item.ownerKind} ({item.ownerName})</span></div>
              </div>
            </div>
          ) : (
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold" style={{
              background: 'rgba(100, 116, 139, 0.1)',
              color: colors.slate[400],
              border: `1px solid ${colors.slate[700]}`,
            }}>
              ⚪ Kubernetes Managed
            </div>
          )}
          {item.deploymentName && (
            <div className="text-[10px] font-mono" style={{ color: colors.slate[400] }}>
              Deployment: <span className="font-bold text-white">{item.deploymentName}</span>
            </div>
          )}
        </div>
      )
    },
    {
      key: 'status',
      header: 'Status & Restarts',
      sortable: true,
      render: (item) => {
        const chipKey = item.status === 'Running' ? 'Running' : item.status === 'Pending' ? 'Pending' : 'Error';
        const chipStyle = colors.statusChips[chipKey as keyof typeof colors.statusChips] || colors.statusChips.Error;
        return (
          <div className="space-y-1.5">
            <span className={`px-2.5 py-1 rounded-md text-xs font-bold inline-block ${item.status !== 'Running' && item.status !== 'Pending' ? 'animate-pulse' : ''}`} style={{
              background: chipStyle.bg,
              color: chipStyle.text,
              border: `1px solid ${chipStyle.border}`,
            }}>
              {item.status}
            </span>
            <div className="text-[11px]" style={{ color: colors.slate[400] }}>
              Restarts: <strong style={{ color: item.restarts > 0 ? colors.semantic.danger.text : colors.slate[400], fontWeight: item.restarts > 0 ? 700 : 400 }}>{item.restarts}</strong>
            </div>
          </div>
        );
      }
    },
  ];

  // --- Actions Renderer ---
  const renderActions = (item: PodItem) => (
    <div className="flex items-center justify-end gap-1.5 flex-wrap">
      {/* Logs */}
      <button
        onClick={() => window.location.href = `/logs?pod=${item.name}&ns=${item.namespace}`}
        className="px-2 py-1 rounded-lg text-xs font-bold flex items-center gap-1 cursor-pointer transition-all hover:brightness-125"
        title="View Live Loki/K8s Logs"
        style={{ background: colors.slate[800], border: `1px solid ${colors.slate[700]}`, color: colors.slate[300] }}
      >
        <FileText className="h-3.5 w-3.5" />
        Logs
      </button>

      {item.gitopsManaged ? (
        // --- GITOPS MANAGED POD ACTIONS ---
        <>
          {/* Restart */}
          {canOperate && (
            <button
              onClick={() => { setSelectedPod(item); setModalAction('restart'); }}
              className="px-2 py-1 rounded-lg text-xs font-bold flex items-center gap-1 cursor-pointer transition-all hover:brightness-125"
              title="Restart Pod (ReplicaSet auto-creates replacement)"
              style={{ background: colors.semantic.info.bg, border: `1px solid ${colors.semantic.info.border}`, color: colors.semantic.info.text }}
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Restart
            </button>
          )}

          {/* Temporary Delete */}
          {canOperate && (
            <button
              onClick={() => setTempDeletePodTarget(item)}
              className="px-2 py-1 rounded-lg text-xs font-bold flex items-center gap-1 cursor-pointer transition-all hover:brightness-125"
              title="Temporary Maintenance Delete (ReplicaSet auto-creates replacement)"
              style={{ background: colors.semantic.danger.bg, border: `1px solid ${colors.semantic.danger.border}`, color: colors.semantic.danger.text }}
            >
              <Trash2 className="h-3.5 w-3.5" />
              Temp Delete
            </button>
          )}

          {/* Open Deployment */}
          <button
            onClick={() => window.location.href = '/deployments'}
            className="px-2 py-1 rounded-lg text-xs font-bold flex items-center gap-1 cursor-pointer transition-all hover:brightness-125"
            title="Open Deployment Control Plane"
            style={{ background: colors.slate[800], border: `1px solid ${colors.slate[700]}`, color: colors.slate[300] }}
          >
            <ExternalLink className="h-3 w-3" />
            Deployment
          </button>

          {/* Open ArgoCD Application */}
          <button
            onClick={() => window.location.href = '/deployments'}
            className="px-2 py-1 rounded-lg text-xs font-bold flex items-center gap-1 cursor-pointer transition-all hover:brightness-125"
            title="Open ArgoCD Application"
            style={{ background: colors.semantic.warning.bg, border: `1px solid ${colors.semantic.warning.border}`, color: colors.semantic.warning.text }}
          >
            <GitBranch className="h-3 w-3" />
            ArgoCD App
          </button>
        </>
      ) : (
        // --- KUBERNETES MANAGED POD ACTIONS ---
        <>
          {canOperate && (
            <>
              <button
                onClick={() => { setSelectedPod(item); setModalAction('restart'); }}
                className="px-2 py-1 rounded-lg text-xs font-bold flex items-center gap-1 cursor-pointer transition-all hover:brightness-125"
                style={{ background: colors.semantic.info.bg, border: `1px solid ${colors.semantic.info.border}`, color: colors.semantic.info.text }}
              >
                <RefreshCw className="h-3.5 w-3.5" />
                Restart
              </button>

              <button
                onClick={() => { setSelectedPod(item); setModalAction('delete'); }}
                className="px-2 py-1 rounded-lg text-xs font-bold flex items-center gap-1 cursor-pointer transition-all hover:brightness-125"
                style={{ background: colors.semantic.danger.bg, border: `1px solid ${colors.semantic.danger.border}`, color: colors.semantic.danger.text }}
              >
                <Trash2 className="h-3.5 w-3.5" />
                Delete
              </button>
            </>
          )}
        </>
      )}
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5" style={{ fontFamily: "'Inter', sans-serif" }}>
            <div className="p-2 rounded-xl" style={{ background: 'rgba(59, 130, 246, 0.12)', border: '1px solid rgba(59, 130, 246, 0.25)' }}>
              <Box className="h-5 w-5" style={{ color: colors.primary[500] }} />
            </div>
            GitOps-Aware Pod Operations
          </h2>
          <p className="text-xs mt-1.5" style={{ color: colors.slate[400] }}>
            Dynamic Pod ownership resolution with safe GitOps lifecycle operations.
          </p>
        </div>
        <button
          onClick={loadPods}
          className="px-3.5 py-2 rounded-xl text-xs font-bold flex items-center gap-1.5 cursor-pointer transition-all hover:brightness-125"
          style={{ background: colors.slate[800], border: `1px solid ${colors.slate[700]}`, color: colors.slate[300] }}
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh Workloads
        </button>
      </div>

      {/* KPI Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Total Pods', value: totalPods, icon: Box, color: colors.primary[500], bg: 'rgba(59, 130, 246, 0.08)', border: 'rgba(59, 130, 246, 0.18)' },
          { label: 'Running', value: runningCount, icon: CheckCircle2, color: colors.semantic.success.text, bg: colors.semantic.success.bg, border: colors.semantic.success.border },
          { label: 'Pending', value: pendingCount, icon: AlertTriangle, color: colors.semantic.warning.text, bg: colors.semantic.warning.bg, border: colors.semantic.warning.border },
          { label: 'Crash / Error', value: crashCount, icon: XCircle, color: colors.semantic.danger.text, bg: colors.semantic.danger.bg, border: colors.semantic.danger.border },
        ].map(kpi => (
          <div key={kpi.label} className="p-4 rounded-2xl transition-all hover:scale-[1.02]" style={{
            background: kpi.bg,
            border: `1px solid ${kpi.border}`,
          }}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: colors.slate[400] }}>{kpi.label}</span>
              <kpi.icon className="h-4 w-4" style={{ color: kpi.color }} />
            </div>
            <div className="text-2xl font-bold" style={{ color: kpi.color }}>{kpi.value}</div>
          </div>
        ))}
      </div>

      {/* Main Data Table */}
      {loading ? (
        <SkeletonLoader type="table" count={6} />
      ) : pods.length === 0 ? (
        <EnterpriseEmptyState
          icon={Box}
          title="No Active Pods"
          description="No active pods were found in the current scope. Adjust namespace scope or verify cluster connectivity."
          actionLabel="Refresh Workloads"
          onAction={loadPods}
        />
      ) : (
        <EnterpriseTable<PodItem>
          columns={columns}
          data={pods}
          searchPlaceholder="Search pods by name, namespace, status..."
          actions={renderActions}
          pageSize={12}
        />
      )}

      {/* Confirmation Modal */}
      {selectedPod && modalAction && (
        <ActionConfirmationModal
          isOpen={true}
          onClose={() => { setSelectedPod(null); setModalAction(null); }}
          onConfirm={handleConfirmAction}
          title={modalAction === 'restart' ? 'Restart Kubernetes Pod' : 'Delete Kubernetes Pod'}
          description={modalAction === 'restart' 
            ? `Are you sure you want to restart pod '${selectedPod.name}'? The container will be terminated and replaced by ReplicaSet controller.`
            : `WARNING: You are about to delete pod '${selectedPod.name}'. This action is immediate.`
          }
          resourceName={selectedPod.name}
          resourceType="Pod"
          namespace={selectedPod.namespace}
          actionType={modalAction}
          loading={actionLoading}
        />
      )}

      {/* Temporary Delete Pod Modal */}
      {tempDeletePodTarget && (
        <TemporaryDeletePodModal
          isOpen={true}
          onClose={() => setTempDeletePodTarget(null)}
          onSuccess={loadPods}
          podName={tempDeletePodTarget.name}
          namespace={tempDeletePodTarget.namespace}
          deploymentName={tempDeletePodTarget.deploymentName}
          applicationName={tempDeletePodTarget.applicationName}
        />
      )}
    </div>
  );
};

export default Pods;
