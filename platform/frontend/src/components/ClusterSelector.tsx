import React, { useState, useRef, useEffect } from 'react';
import { Server, ChevronDown, Check } from 'lucide-react';
import { useCluster, ClusterItem } from '../context/ClusterContext';

export const ClusterSelector: React.FC = () => {
  const { activeCluster, clusters, setActiveCluster } = useCluster();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = (cluster: ClusterItem) => {
    setActiveCluster(cluster);
    setIsOpen(false);
    // Reload page data to instantly fetch resources for target cluster
    window.location.reload();
  };

  return (
    <div className="relative inline-block text-left" ref={dropdownRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-slate-900/90 border border-slate-800 text-xs font-semibold text-slate-200 hover:bg-slate-800 hover:border-slate-700 transition cursor-pointer shadow-sm"
      >
        <Server className="h-3.5 w-3.5 text-blue-400" />
        <span className="truncate max-w-[140px]">
          {activeCluster ? activeCluster.name : 'No Cluster'}
        </span>
        {activeCluster ? (
          <span className="flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span>{activeCluster.provider || 'K8s'}</span>
          </span>
        ) : (
          <span className="flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-400 border border-slate-700">
            <span>Offline</span>
          </span>
        )}
        <ChevronDown className={`h-3.5 w-3.5 text-slate-400 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-64 rounded-xl bg-slate-900 border border-slate-800 shadow-2xl z-50 overflow-hidden py-1 divide-y divide-slate-800/60">
          <div className="px-3 py-2 bg-slate-950/50">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Kubernetes Clusters</p>
            <p className="text-[11px] text-slate-500">
              {activeCluster ? `Active context: ${activeCluster.context_name}` : 'No clusters registered'}
            </p>
          </div>

          <div className="py-1 max-h-56 overflow-y-auto">
            {clusters.length === 0 ? (
              <div className="p-4 text-center space-y-2">
                <p className="text-xs text-slate-400">No clusters registered yet.</p>
                <a
                  href="/clusters"
                  className="inline-block px-3 py-1 rounded-lg text-xs font-semibold bg-blue-600 hover:bg-blue-500 text-white transition"
                >
                  + Add Cluster
                </a>
              </div>
            ) : (
              clusters.map((cluster) => {
                const isSelected = activeCluster?.id === cluster.id;
                return (
                  <button
                    key={cluster.id}
                    onClick={() => handleSelect(cluster)}
                    className={`w-full text-left px-3 py-2 flex items-center justify-between hover:bg-slate-800/80 transition cursor-pointer ${
                      isSelected ? 'bg-blue-600/10 border-l-2 border-blue-500' : ''
                    }`}
                  >
                    <div className="space-y-0.5 truncate pr-2">
                      <div className="flex items-center space-x-2">
                        <span className="text-xs font-semibold text-slate-200 truncate">{cluster.name}</span>
                        {cluster.is_default && (
                          <span className="text-[9px] px-1 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">Default</span>
                        )}
                      </div>
                      <p className="text-[10px] text-slate-400 truncate font-mono">
                        {cluster.provider} • {cluster.environment}
                      </p>
                    </div>
                    {isSelected && <Check className="h-4 w-4 text-blue-400 flex-shrink-0" />}
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
};
