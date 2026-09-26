import React, { useEffect, useState } from 'react';
import { EnterpriseTable, ColumnDef } from '../components/EnterpriseTable';
import { SkeletonLoader } from '../components/SkeletonLoader';
import { EnterpriseEmptyState } from '../components/EnterpriseEmptyState';
import { api } from '../services/api';
import { RefreshCw, Play, X, History, Scale, Trash2, GitBranch, ShieldOff, Layers, CheckCircle2, AlertTriangle, Clock } from 'lucide-react';
import { useScope } from '../context/ScopeContext';
import { ActionConfirmationModal } from '../components/ActionConfirmationModal';
import { DisconnectGitOpsModal } from '../components/DisconnectGitOpsModal';
import { TemporaryDeleteModal } from '../components/TemporaryDeleteModal';
import { ReconnectGitOpsModal } from '../components/ReconnectGitOpsModal';
import { colors } from '../theme/designTokens';

interface DeploymentItem {
  name: string;
  namespace: string;
  status: string;
  replicas: number;
  ready_replicas: number;
  gitopsManaged: boolean;
  manager: string;
  argocd_app_name?: string;
  repo_url?: string;
  targetRevision?: string;
  sync_status?: string;
  health_status?: string;
}

const Deployments: React.FC = () => {
  const [deployments, setDeployments] = useState<DeploymentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState<string | null>(null);
  
  // Selected app for details side panel drawer
  const [selectedApp, setSelectedApp] = useState<DeploymentItem | null>(null);
  const [historyLogs, setHistoryLogs] = useState<any[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  
  // Action Modals State
  const [modalTarget, setModalTarget] = useState<DeploymentItem | null>(null);
  const [modalAction, setModalAction] = useState<'restart' | 'scale' | 'rollback' | 'delete' | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  // Sprint 15.1 & 15.3 GitOps Modals State
  const [disconnectModalTarget, setDisconnectModalTarget] = useState<DeploymentItem | null>(null);
  const [tempDeleteModalTarget, setTempDeleteModalTarget] = useState<DeploymentItem | null>(null);
  const [reconnectModalTarget, setReconnectModalTarget] = useState<DeploymentItem | null>(null);

  const userRole = localStorage.getItem('user_role') || 'Viewer';
  const isDevOpsOrAdmin = ['Administrator', 'Platform Engineer', 'DevOps Engineer'].includes(userRole);
  const isAdmin = userRole === 'Administrator' || userRole === 'Platform Engineer';
  const { getScopeParams } = useScope();

  const fetchDeployments = async () => {
    try {
      const data = await api.getDeployments(undefined, getScopeParams());
      setDeployments(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDeployments();
  }, [JSON.stringify(getScopeParams())]);

  const handleSync = async (item: DeploymentItem) => {
    const appName = item.argocd_app_name || item.name;
    setTriggering(appName);
    try {
      await api.syncApplication(appName);
      await fetchDeployments();
    } catch (e: any) {
      alert(e.message || 'ArgoCD sync failed.');
    } finally {
      setTriggering(null);
    }
  };

  const handleOpenDetails = async (item: DeploymentItem) => {
    setSelectedApp(item);
    setHistoryLoading(true);
    try {
      const appName = item.argocd_app_name || item.name;
      const logs = await api.getApplicationHistory(appName);
      setHistoryLogs(logs);
    } catch (e) {
      console.error(e);
    } finally {
      setHistoryLoading(false);
    }
  };

  const handleConfirmAction = async (paramValue?: any) => {
    if (!modalTarget || !modalAction) return;
    setActionLoading(true);
    try {
      if (modalAction === 'restart') {
        await api.restartDeployment(modalTarget.namespace, modalTarget.name);
      } else if (modalAction === 'scale') {
        const replicas = typeof paramValue === 'number' ? paramValue : (parseInt(paramValue, 10) || 1);
        await api.scaleDeployment(modalTarget.namespace, modalTarget.name, replicas);
      } else if (modalAction === 'rollback') {
        await api.rollbackDeployment(modalTarget.namespace, modalTarget.name);
      } else if (modalAction === 'delete') {
        await api.deleteDeployment(modalTarget.namespace, modalTarget.name, false);
      }
      setModalTarget(null);
      setModalAction(null);
      await fetchDeployments();
    } catch (e: any) {
      console.error("Deployment action error:", e);
      alert(e.message || 'Deployment action failed. Please check cluster RBAC or GitOps sync.');
    } finally {
      setActionLoading(false);
    }
  };

  // --- Derived KPI Stats ---
  const totalDeployments = deployments.length;
  const healthyCount = deployments.filter(d => d.ready_replicas >= d.replicas && d.replicas > 0).length;
  const degradedCount = deployments.filter(d => d.ready_replicas < d.replicas && d.ready_replicas > 0).length;
  const gitopsCount = deployments.filter(d => d.gitopsManaged).length;

  // --- EnterpriseTable Column Definitions ---
  const columns: ColumnDef<DeploymentItem>[] = [
    {
      key: 'name',
      header: 'Deployment',
      sortable: true,
      render: (item) => (
        <div className="space-y-1" data-ai-resource data-ai-name={item.name} data-ai-kind="deployment" data-ai-namespace={item.namespace}>
          <div className="font-bold text-white text-sm flex items-center gap-2 cursor-context-menu" title="Right-click for AI Actions" style={{ fontFamily: "'Fira Code', monospace" }}>
            {item.name}
            <span className="text-[10px] px-1.5 py-0.5 rounded-md font-mono" style={{
              background: colors.slate[800],
              color: colors.slate[400],
            }}>
              {item.namespace}
            </span>
          </div>
          <div className="text-[11px] flex items-center gap-3" style={{ color: colors.slate[400] }}>
            <span>Replicas: <strong className="text-white">{item.ready_replicas}/{item.replicas}</strong></span>
          </div>
        </div>
      )
    },
    {
      key: 'gitopsManaged',
      header: 'Management',
      render: (item) => (
        <div className="space-y-1">
          {item.gitopsManaged ? (
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold group relative cursor-pointer" style={{
              background: colors.semantic.success.bg,
              color: colors.semantic.success.text,
              border: `1px solid ${colors.semantic.success.border}`,
            }}>
              <span className="h-2 w-2 rounded-full animate-pulse" style={{ background: colors.semantic.success.badgeBg }} />
              GitOps Managed

              {/* Detailed GitOps Card Tooltip */}
              <div className="hidden group-hover:block absolute top-full left-0 mt-2 z-40 w-72 p-3 rounded-xl shadow-2xl space-y-2 text-[11px]" style={{
                background: colors.slate[900],
                border: `1px solid ${colors.slate[800]}`,
                color: colors.slate[300],
              }}>
                <div className="flex items-center justify-between pb-1.5 font-bold text-white" style={{ borderBottom: `1px solid ${colors.slate[800]}` }}>
                  <span>ArgoCD Application Info</span>
                  <span className="text-[10px] uppercase" style={{ color: colors.semantic.success.text }}>{item.sync_status || 'Synced'}</span>
                </div>
                <div className="space-y-1 font-mono text-[10px]">
                  <div><span style={{ color: colors.slate[500] }}>Manager:</span> <strong className="text-white">{item.manager}</strong></div>
                  <div><span style={{ color: colors.slate[500] }}>Application:</span> <strong style={{ color: colors.semantic.warning.text }}>{item.argocd_app_name || item.name}</strong></div>
                  <div><span style={{ color: colors.slate[500] }}>Repository:</span> <span className="truncate block" style={{ color: colors.semantic.info.text }}>{item.repo_url || 'GitHub (main)'}</span></div>
                  <div><span style={{ color: colors.slate[500] }}>Revision:</span> <span style={{ color: colors.slate[300] }}>{item.targetRevision || 'HEAD'}</span></div>
                  <div><span style={{ color: colors.slate[500] }}>Health:</span> <span style={{ color: colors.semantic.success.text }}>{item.health_status || 'Healthy'}</span></div>
                </div>
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
        </div>
      )
    },
    {
      key: 'sync_status',
      header: 'Sync & Health',
      sortable: true,
      render: (item) => {
        const isSynced = item.sync_status === 'Synced' || !item.gitopsManaged;
        const chipStyle = isSynced ? colors.statusChips.Synced : colors.statusChips.OutOfSync;
        return (
          <span className="px-2.5 py-1 rounded-md text-[11px] font-bold uppercase tracking-wider" style={{
            background: chipStyle.bg,
            color: chipStyle.text,
            border: `1px solid ${chipStyle.border}`,
          }}>
            {item.sync_status || 'In-Sync'}
          </span>
        );
      }
    },
  ];

  // --- Actions Renderer ---
  const renderActions = (item: DeploymentItem) => (
    <div className="flex items-center justify-end gap-1.5 flex-wrap">
      {item.gitopsManaged ? (
        <>
          {/* Runtime Operations: Scale Replicas */}
          {isDevOpsOrAdmin && (
            <button
              onClick={() => { setModalTarget(item); setModalAction('scale'); }}
              className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-bold cursor-pointer transition-all hover:brightness-125"
              title="Scale Deployment Replicas (Upscale / Downscale)"
              style={{ background: 'rgba(99, 102, 241, 0.1)', border: '1px solid rgba(99, 102, 241, 0.2)', color: '#818cf8' }}
            >
              <Scale className="h-3 w-3" />
              Scale
            </button>
          )}

          {/* Runtime Operations: Restart Rollout */}
          {isDevOpsOrAdmin && (
            <button
              onClick={() => { setModalTarget(item); setModalAction('restart'); }}
              className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-bold cursor-pointer transition-all hover:brightness-125"
              title="Runtime Operation: Restart Rollout"
              style={{ background: colors.semantic.info.bg, border: `1px solid ${colors.semantic.info.border}`, color: colors.semantic.info.text }}
            >
              <RefreshCw className="h-3 w-3" />
              Restart
            </button>
          )}

          {/* GitOps Operations: Sync */}
          {isDevOpsOrAdmin && (
            <button
              onClick={() => handleSync(item)}
              disabled={triggering === (item.argocd_app_name || item.name)}
              className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-bold cursor-pointer transition-all hover:brightness-125 disabled:opacity-50"
              title="GitOps Operation: Sync Application with Git Repo"
              style={{ background: colors.semantic.success.bg, border: `1px solid ${colors.semantic.success.border}`, color: colors.semantic.success.text }}
            >
              {triggering === (item.argocd_app_name || item.name) ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
              Sync
            </button>
          )}

          {/* GitOps Operations: History */}
          <button
            onClick={() => handleOpenDetails(item)}
            className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-bold cursor-pointer transition-all hover:brightness-125"
            title="GitOps Operation: View Revisions History"
            style={{ background: colors.slate[800], border: `1px solid ${colors.slate[700]}`, color: colors.slate[300] }}
          >
            <History className="h-3 w-3" />
            History
          </button>

          {/* Danger Zone: Temporary Delete */}
          {isDevOpsOrAdmin && (
            <button
              onClick={() => setTempDeleteModalTarget(item)}
              className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-bold cursor-pointer transition-all hover:brightness-125"
              title="Danger Zone: Temporary Maintenance Delete (Self-Heals)"
              style={{ background: colors.semantic.danger.bg, border: `1px solid ${colors.semantic.danger.border}`, color: colors.semantic.danger.text }}
            >
              <Trash2 className="h-3 w-3" />
              Temp Delete
            </button>
          )}

          {/* Danger Zone: Disconnect from GitOps (Admin Only) */}
          {isAdmin && (
            <button
              onClick={() => setDisconnectModalTarget(item)}
              className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-bold cursor-pointer transition-all hover:brightness-125"
              title="Danger Zone: Disconnect from GitOps (Unlocks K8s Lifecycle Actions)"
              style={{ background: colors.semantic.warning.bg, border: `1px solid ${colors.semantic.warning.border}`, color: colors.semantic.warning.text }}
            >
              <ShieldOff className="h-3 w-3" />
              Disconnect
            </button>
          )}

          {/* Protected indicator */}
          <span className="text-[10px] italic flex items-center gap-0.5" style={{ color: colors.slate[500] }}>
            🔒 GitOps Protected
          </span>
        </>
      ) : (
        // --- KUBERNETES MANAGED WORKLOAD OPERATIONS ---
        <>
          {/* Scale */}
          {isDevOpsOrAdmin && (
            <button
              onClick={() => { setModalTarget(item); setModalAction('scale'); }}
              className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-bold cursor-pointer transition-all hover:brightness-125"
              style={{ background: 'rgba(99, 102, 241, 0.1)', border: '1px solid rgba(99, 102, 241, 0.2)', color: '#818cf8' }}
            >
              <Scale className="h-3 w-3" />
              Scale
            </button>
          )}

          {/* Restart */}
          {isDevOpsOrAdmin && (
            <button
              onClick={() => { setModalTarget(item); setModalAction('restart'); }}
              className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-bold cursor-pointer transition-all hover:brightness-125"
              style={{ background: colors.semantic.info.bg, border: `1px solid ${colors.semantic.info.border}`, color: colors.semantic.info.text }}
            >
              <RefreshCw className="h-3 w-3" />
              Restart
            </button>
          )}

          {/* Reconnect to GitOps */}
          {isDevOpsOrAdmin && (
            <button
              onClick={() => setReconnectModalTarget(item)}
              className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-bold cursor-pointer transition-all hover:brightness-125"
              title="Reconnect Deployment to GitOps Management"
              style={{ background: colors.semantic.success.bg, border: `1px solid ${colors.semantic.success.border}`, color: colors.semantic.success.text }}
            >
              <GitBranch className="h-3 w-3" />
              Reconnect to GitOps
            </button>
          )}

          {/* Permanent Delete */}
          {isAdmin && (
            <button
              onClick={() => { setModalTarget(item); setModalAction('delete'); }}
              className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-bold cursor-pointer transition-all hover:brightness-125"
              style={{ background: colors.semantic.danger.bg, border: `1px solid ${colors.semantic.danger.border}`, color: colors.semantic.danger.text }}
            >
              <Trash2 className="h-3 w-3" />
              Delete
            </button>
          )}
        </>
      )}
    </div>
  );

  return (
    <div className="relative">
      <div className="space-y-6">
        {/* Page Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5" style={{ fontFamily: "'Inter', sans-serif" }}>
              <div className="p-2 rounded-xl" style={{ background: 'rgba(59, 130, 246, 0.12)', border: '1px solid rgba(59, 130, 246, 0.25)' }}>
                <GitBranch className="h-5 w-5" style={{ color: colors.primary[500] }} />
              </div>
              GitOps Operations Control Plane
            </h2>
            <p className="text-xs mt-1.5" style={{ color: colors.slate[400] }}>
              Dynamic GitOps ownership detection with RBAC-enforced operational guardrails.
            </p>
          </div>
          <button
            onClick={fetchDeployments}
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
            { label: 'Total Deployments', value: totalDeployments, icon: Layers, color: colors.primary[500], bg: 'rgba(59, 130, 246, 0.08)', border: 'rgba(59, 130, 246, 0.18)' },
            { label: 'Healthy', value: healthyCount, icon: CheckCircle2, color: colors.semantic.success.text, bg: colors.semantic.success.bg, border: colors.semantic.success.border },
            { label: 'Degraded', value: degradedCount, icon: AlertTriangle, color: colors.semantic.warning.text, bg: colors.semantic.warning.bg, border: colors.semantic.warning.border },
            { label: 'GitOps Managed', value: gitopsCount, icon: GitBranch, color: '#a78bfa', bg: 'rgba(139, 92, 246, 0.08)', border: 'rgba(139, 92, 246, 0.18)' },
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
        ) : deployments.length === 0 ? (
          <EnterpriseEmptyState
            icon={GitBranch}
            title="No Deployments Found"
            description="No deployments were found in the active scope. Adjust your namespace scope or check cluster connectivity."
            actionLabel="Refresh Workloads"
            onAction={fetchDeployments}
          />
        ) : (
          <EnterpriseTable<DeploymentItem>
            columns={columns}
            data={deployments}
            searchPlaceholder="Search deployments by name, namespace, status..."
            actions={renderActions}
            pageSize={12}
          />
        )}
      </div>

      {/* Action Confirmation Modal */}
      {modalTarget && modalAction && (
        <ActionConfirmationModal
          isOpen={true}
          onClose={() => { setModalTarget(null); setModalAction(null); }}
          onConfirm={handleConfirmAction}
          title={
            modalAction === 'scale' ? 'Scale Deployment Replicas' :
            modalAction === 'restart' ? 'Restart Deployment Rollout' :
            modalAction === 'rollback' ? 'Rollback Deployment Revision' :
            'Delete Deployment Workload'
          }
          description={
            modalAction === 'scale' ? `Specify the desired target number of replicas for deployment '${modalTarget.name}'.` :
            modalAction === 'restart' ? `Are you sure you want to trigger a rolling restart for deployment '${modalTarget.name}'?` :
            modalAction === 'rollback' ? `Are you sure you want to undo rollout for deployment '${modalTarget.name}' to the previous revision?` :
            `WARNING: You are about to permanently delete deployment '${modalTarget.name}'.`
          }
          resourceName={modalTarget.name}
          resourceType="Deployment"
          namespace={modalTarget.namespace}
          actionType={modalAction}
          defaultValue={modalAction === 'scale' ? modalTarget.replicas : undefined}
          loading={actionLoading}
        />
      )}

      {/* Sprint 15.1 Disconnect from GitOps Modal */}
      {disconnectModalTarget && (
        <DisconnectGitOpsModal
          isOpen={true}
          onClose={() => setDisconnectModalTarget(null)}
          onSuccess={fetchDeployments}
          appName={disconnectModalTarget.argocd_app_name || disconnectModalTarget.name}
          deploymentName={disconnectModalTarget.name}
          namespace={disconnectModalTarget.namespace}
        />
      )}

      {/* Sprint 15.1 Temporary Delete Modal */}
      {tempDeleteModalTarget && (
        <TemporaryDeleteModal
          isOpen={true}
          onClose={() => setTempDeleteModalTarget(null)}
          onSuccess={fetchDeployments}
          onOpenDisconnect={() => setDisconnectModalTarget(tempDeleteModalTarget)}
          deploymentName={tempDeleteModalTarget.name}
          namespace={tempDeleteModalTarget.namespace}
        />
      )}

      {/* Sprint 15.3 Reconnect to GitOps Modal */}
      {reconnectModalTarget && (
        <ReconnectGitOpsModal
          isOpen={true}
          onClose={() => setReconnectModalTarget(null)}
          onSuccess={fetchDeployments}
          deploymentName={reconnectModalTarget.name}
          namespace={reconnectModalTarget.namespace}
        />
      )}

      {/* Details Sidebar Overlay Drawer */}
      {selectedApp && (
        <div className="fixed inset-y-0 right-0 z-50 w-full sm:w-[500px] flex flex-col justify-between transition-transform duration-300" style={{
          background: colors.slate[900],
          borderLeft: `1px solid ${colors.slate[800]}`,
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
        }}>
          <div className="space-y-6 overflow-y-auto p-8 pr-4 scrollbar-thin">
            <div className="flex items-center justify-between pb-4" style={{ borderBottom: `1px solid ${colors.slate[800]}` }}>
              <div>
                <h3 className="text-xl font-bold text-white">{selectedApp.name}</h3>
                <p className="text-xs mt-0.5" style={{ color: colors.slate[400] }}>GitOps Revision Timeline & History</p>
              </div>
              <button 
                onClick={() => setSelectedApp(null)}
                className="p-1.5 rounded-lg cursor-pointer transition-colors hover:bg-slate-800"
                style={{ color: colors.slate[400] }}
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {historyLoading ? (
              <SkeletonLoader type="list" count={4} />
            ) : (
              <div className="space-y-4">
                <h4 className="text-xs font-bold uppercase tracking-wider" style={{ color: colors.slate[400] }}>Commit History Logs</h4>
                {historyLogs.length === 0 ? (
                  <div className="text-center py-8">
                    <Clock className="h-8 w-8 mx-auto mb-2" style={{ color: colors.slate[600] }} />
                    <p className="text-xs" style={{ color: colors.slate[500] }}>No revision history available.</p>
                  </div>
                ) : (
                  historyLogs.map((log) => (
                    <div key={log.id} className="p-4 rounded-xl space-y-2 text-xs" style={{
                      background: colors.slate[950],
                      border: `1px solid ${colors.slate[800]}`,
                    }}>
                      <div className="flex items-center justify-between">
                        <span className="font-mono font-bold" style={{ color: colors.semantic.info.text }}>Rev #{log.id} ({log.revision.substring(0, 7)})</span>
                        <span className="text-[10px]" style={{ color: colors.slate[500] }}>{new Date(log.deployedAt || Date.now()).toLocaleString()}</span>
                      </div>
                      <p className="font-medium" style={{ color: colors.slate[300] }}>"{log.commitMessage || 'Automated GitOps Sync'}"</p>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default Deployments;
