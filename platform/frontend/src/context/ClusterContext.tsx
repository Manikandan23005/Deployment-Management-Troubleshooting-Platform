import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { api } from '../services/api';

export interface ClusterItem {
  id: string;
  name: string;
  description?: string;
  environment: string;
  provider: string;
  context_name: string;
  api_server?: string;
  authentication_type?: string;
  default_namespace?: string;
  status: string;
  is_default?: boolean;
  argocd_url?: string;
  prometheus_url?: string;
  loki_url?: string;
  created_at?: string;
  updated_at?: string;
}

interface ClusterContextType {
  activeCluster: ClusterItem | null;
  clusters: ClusterItem[];
  setActiveCluster: (cluster: ClusterItem) => void;
  refreshClusters: () => Promise<void>;
  loading: boolean;
  initialized: boolean;
}

const ClusterContext = createContext<ClusterContextType | undefined>(undefined);

export const ClusterProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [clusters, setClusters] = useState<ClusterItem[]>([]);
  const [activeCluster, setActiveClusterState] = useState<ClusterItem | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [initialized, setInitialized] = useState<boolean>(false);

  const refreshClusters = async () => {
    try {
      setLoading(true);
      const res = await api.getClusters();
      if (res && res.data && res.data.success && Array.isArray(res.data.data)) {
        const list: ClusterItem[] = res.data.data;
        setClusters(list);

        const savedId = localStorage.getItem('nexus_active_cluster_id');
        let selected = list.find((c) => c.id === savedId);
        if (!selected) {
          selected = list.find((c) => c.is_default) || list[0] || null;
        }

        if (selected) {
          setActiveClusterState(selected);
          localStorage.setItem('nexus_active_cluster_id', selected.id);
        } else if (list.length > 0) {
          setActiveClusterState(list[0]);
          localStorage.setItem('nexus_active_cluster_id', list[0].id);
        } else {
          setActiveClusterState(null);
          localStorage.removeItem('nexus_active_cluster_id');
        }
      } else {
        setClusters([]);
        setActiveClusterState(null);
      }
    } catch (err) {
      console.warn('Failed to load clusters:', err);
      setClusters([]);
      setActiveClusterState(null);
    } finally {
      setLoading(false);
      setInitialized(true);
    }
  };

  const setActiveCluster = (cluster: ClusterItem) => {
    setActiveClusterState(cluster);
    localStorage.setItem('nexus_active_cluster_id', cluster.id);
  };

  useEffect(() => {
    refreshClusters();
    const handleStorage = () => {
      refreshClusters();
    };
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, []);

  return (
    <ClusterContext.Provider value={{ activeCluster, clusters, setActiveCluster, refreshClusters, loading, initialized }}>
      {children}
    </ClusterContext.Provider>
  );
};

export const useCluster = (): ClusterContextType => {
  const context = useContext(ClusterContext);
  if (!context) {
    throw new Error('useCluster must be used within a ClusterProvider');
  }
  return context;
};
