import React, { useState, useEffect } from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';
import { 
  LayoutDashboard, GitBranch, Cpu, Layers, BarChart3, 
  Terminal, AlertTriangle, Bot, Settings, Sun, Moon, Menu, X, TerminalSquare, Server,
  Users, Shield, Grid, ShieldAlert, Search, Command, ShieldCheck, Cloud
} from 'lucide-react';
import { api } from '../services/api';
import { useScope, ScopeMode, InfrastructureDomain } from '../context/ScopeContext';

import { ClusterSelector } from '../components/ClusterSelector';
import { ResourceContextMenu } from '../components/ResourceContextMenu';
import { CommandPalette } from '../components/CommandPalette';

const DashboardLayout: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [darkMode, setDarkMode] = useState(true);
  const [cmdPaletteOpen, setCmdPaletteOpen] = useState(false);
  const location = useLocation();

  const {
    scopeMode,
    setScopeMode,
    selectedNamespace,
    setSelectedNamespace,
    selectedApp,
    setSelectedApp,
    selectedDomain,
    setSelectedDomain
  } = useScope();

  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [darkMode]);

  // Global Ctrl + K / Cmd + K listener
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        setCmdPaletteOpen(prev => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const userRole = localStorage.getItem('user_role') || 'Viewer';

  let allNavItems = [];
  if (userRole === 'Administrator' || userRole === 'Platform Engineer') {
    allNavItems = [
      { path: '/overview', label: 'Dashboard', icon: LayoutDashboard },
      { path: '/clusters', label: 'Clusters', icon: Server },
      { path: '/aws/accounts', label: 'AWS Accounts', icon: Cloud },
      { path: '/ai', label: 'AI Operations', icon: Bot },
      { path: '/deployments', label: 'Deployments', icon: GitBranch },
      { path: '/pods', label: 'Pods', icon: Cpu },
      { path: '/nodes', label: 'Nodes', icon: Server },
      { path: '/namespaces', label: 'Namespaces', icon: Layers },
      { path: '/metrics', label: 'Metrics', icon: BarChart3 },
      { path: '/logs', label: 'Logs', icon: Terminal },
      { path: '/alerts', label: 'Alerts', icon: AlertTriangle },
      { path: '/admin/users', label: 'Users', icon: Users },
      { path: '/admin/roles', label: 'Roles', icon: Shield },
      { path: '/admin/permissions', label: 'Permissions Matrix', icon: Grid },
      { path: '/admin/audit', label: 'Audit Logs', icon: ShieldAlert },
      { path: '/admin/verification', label: 'Verification', icon: ShieldCheck },
      { path: '/settings', label: 'Settings', icon: Settings },
    ];
  } else if (userRole === 'DevOps Engineer') {
    allNavItems = [
      { path: '/overview', label: 'Dashboard', icon: LayoutDashboard },
      { path: '/clusters', label: 'Clusters', icon: Server },
      { path: '/aws/accounts', label: 'AWS Accounts', icon: Cloud },
      { path: '/ai', label: 'AI Operations', icon: Bot },
      { path: '/deployments', label: 'Deployments', icon: GitBranch },
      { path: '/pods', label: 'Pods', icon: Cpu },
      { path: '/nodes', label: 'Nodes', icon: Server },
      { path: '/namespaces', label: 'Namespaces', icon: Layers },
      { path: '/metrics', label: 'Metrics', icon: BarChart3 },
      { path: '/logs', label: 'Logs', icon: Terminal },
      { path: '/alerts', label: 'Alerts', icon: AlertTriangle },
    ];
  } else if (userRole === 'Developer') {
    allNavItems = [
      { path: '/overview', label: 'Dashboard', icon: LayoutDashboard },
      { path: '/ai', label: 'AI Operations', icon: Bot },
      { path: '/deployments', label: 'Deployments', icon: GitBranch },
      { path: '/logs', label: 'Logs', icon: Terminal },
    ];
  } else {
    // Viewer
    allNavItems = [
      { path: '/overview', label: 'Dashboard', icon: LayoutDashboard },
      { path: '/metrics', label: 'Monitoring', icon: BarChart3 },
      { path: '/ai', label: 'AI Operations', icon: Bot },
    ];
  }

  const currentNav = allNavItems.find(item => item.path === location.pathname);
  const breadcrumb = currentNav ? currentNav.label : 'Dashboard';

  const knownApps = [
    'auth-service', 'frontend-service', 'gateway-service',
    'notification-service', 'orders-service', 'payment-service',
    'products-service', 'users-service'
  ];

  return (
    <div className="min-h-screen flex bg-slate-50 dark:bg-[#0b0f19] text-slate-900 dark:text-slate-100 font-sans transition-colors duration-200">
      {/* --- Sidebar Navigation --- */}
      <aside 
        className={`fixed inset-y-0 left-0 z-40 bg-white/80 dark:bg-slate-900/80 border-r border-slate-200 dark:border-slate-800 backdrop-blur-xl flex flex-col justify-between transition-all duration-300 ${
          sidebarOpen ? 'w-64' : 'w-20'
        }`}
      >
        <div className="space-y-6">
          {/* Brand Header */}
          <div className="h-16 flex items-center px-6 border-b border-slate-200 dark:border-slate-800">
            <div className="flex items-center gap-3">
              <div className="h-9 w-9 rounded-xl bg-blue-600 flex items-center justify-center text-white font-bold shadow-lg shadow-blue-500/20 flex-shrink-0">
                <TerminalSquare className="h-5 w-5" />
              </div>
              {sidebarOpen && (
                <div className="flex flex-col">
                  <span className="font-bold text-base tracking-wide bg-gradient-to-r from-blue-600 to-indigo-600 dark:from-blue-400 dark:to-indigo-400 bg-clip-text text-transparent">
                    DevOps Nexus
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="px-3 space-y-1.5 overflow-y-auto max-h-[calc(100vh-10rem)]">
            {allNavItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`flex items-center gap-3 px-3.5 py-2.5 rounded-xl font-semibold text-sm transition-all duration-200 ${
                    isActive 
                      ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20' 
                      : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800/60 hover:text-slate-900 dark:hover:text-white'
                  }`}
                >
                  <Icon className="h-4.5 w-4.5 flex-shrink-0" />
                  {sidebarOpen && <span>{item.label}</span>}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Sidebar Toggle Button */}
        <div className="p-4 border-t border-slate-200 dark:border-slate-800">
          <button 
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="w-full flex items-center justify-center p-3 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700/80 transition-all"
          >
            {sidebarOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>
        </div>
      </aside>

      {/* --- Page Main Viewport --- */}
      <div className={`flex-1 flex flex-col transition-all duration-300 ${sidebarOpen ? 'pl-64' : 'pl-20'}`}>
        
        {/* Top Navbar with Operations Scope Controls & Spotlight Search */}
        <header className="h-16 flex items-center justify-between px-6 bg-white/60 dark:bg-slate-900/60 border-b border-slate-200 dark:border-slate-800 backdrop-blur-md sticky top-0 z-30 min-w-0">
          
          {/* Left: Clean Breadcrumbs & Command Palette Trigger */}
          <div className="flex items-center gap-4 text-sm flex-shrink-0">
            <span className="text-slate-400 font-medium tracking-wide flex items-center gap-1.5">
              <span>Platform</span> / <strong className="text-slate-800 dark:text-white font-bold">{breadcrumb}</strong>
            </span>

            {/* Spotlight Command Palette Trigger */}
            <button
              onClick={() => setCmdPaletteOpen(true)}
              className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-100 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700/80 text-xs text-slate-400 hover:text-slate-200 hover:bg-slate-200 dark:hover:bg-slate-800 transition-all font-mono"
            >
              <Search className="h-3.5 w-3.5 text-indigo-400" />
              <span>Search or type command...</span>
              <kbd className="px-1.5 py-0.5 text-[10px] bg-slate-200 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded text-slate-400 flex items-center gap-0.5">
                <Command className="h-2.5 w-2.5" /> K
              </kbd>
            </button>
          </div>

          {/* Right: Operations Controls & User Profile */}
          <div className="flex items-center gap-2.5 flex-shrink max-w-[calc(100%-200px)] overflow-x-auto py-1 no-scrollbar">
            {/* Global Multi-Cluster Selector */}
            <ClusterSelector />

            {/* Scope Mode Dropdown */}
            <select
              value={scopeMode}
              onChange={(e) => setScopeMode(e.target.value as ScopeMode)}
              className="px-3 py-1.5 rounded-xl bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs font-bold text-slate-700 dark:text-slate-200 focus:outline-none focus:border-blue-500 cursor-pointer"
            >
              <option value="cluster">🌐 Scope: Entire Cluster</option>
              <option value="namespace">📦 Scope: Namespace</option>
              <option value="app">🚀 Scope: Application</option>
              <option value="infra">⚙ Scope: Infrastructure</option>
            </select>

            {/* Secondary Selector: Namespace */}
            {(scopeMode === 'namespace' || scopeMode === 'app') && (
              <select
                value={selectedNamespace}
                onChange={(e) => setSelectedNamespace(e.target.value)}
                className="px-3 py-1.5 rounded-xl bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs font-bold text-slate-700 dark:text-slate-200 focus:outline-none focus:border-blue-500 cursor-pointer"
              >
                <option value="devops-nexus-prod">Namespace: devops-nexus-prod</option>
                <option value="monitoring">Namespace: monitoring</option>
                <option value="logging-lab">Namespace: logging-lab</option>
                <option value="argocd">Namespace: argocd</option>
                <option value="ingress-nginx">Namespace: ingress-nginx</option>
                <option value="kube-system">Namespace: kube-system</option>
                <option value="default">Namespace: default</option>
              </select>
            )}

            {/* Secondary Selector: Application */}
            {scopeMode === 'app' && (
              <select
                value={selectedApp}
                onChange={(e) => setSelectedApp(e.target.value)}
                className="px-3 py-1.5 rounded-xl bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs font-bold text-slate-700 dark:text-slate-200 focus:outline-none focus:border-blue-500 cursor-pointer"
              >
                {knownApps.map(a => (
                  <option key={a} value={a}>App: {a}</option>
                ))}
              </select>
            )}

            {/* Secondary Selector: Infrastructure Domain */}
            {scopeMode === 'infra' && (
              <select
                value={selectedDomain}
                onChange={(e) => setSelectedDomain(e.target.value as InfrastructureDomain)}
                className="px-3 py-1.5 rounded-xl bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs font-bold text-slate-700 dark:text-slate-200 focus:outline-none focus:border-blue-500 cursor-pointer"
              >
                <option value="monitoring">Domain: Monitoring</option>
                <option value="logging">Domain: Logging</option>
                <option value="gitops">Domain: GitOps</option>
                <option value="networking">Domain: Networking</option>
                <option value="storage">Domain: Storage</option>
              </select>
            )}

            {/* System Health Badge */}
            <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-500 text-xs font-semibold">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              Healthy
            </div>

            {/* Dark Mode Toggle */}
            <button 
              onClick={() => setDarkMode(!darkMode)}
              className="p-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-all duration-200"
            >
              {darkMode ? <Sun className="h-4 w-4 text-amber-500" /> : <Moon className="h-4 w-4 text-indigo-500" />}
            </button>

            {/* User Profile & Logout */}
            <div className="flex items-center gap-3 pl-2 border-l border-slate-200 dark:border-slate-800">
              <div className="text-right hidden sm:block">
                <div className="text-xs font-bold text-slate-800 dark:text-white capitalize">
                  {localStorage.getItem('username') || 'Operator'}
                </div>
                <div className="text-[10px] font-semibold text-blue-500">
                  {localStorage.getItem('user_role') || 'Viewer'}
                </div>
              </div>
              <div className="h-8 w-8 rounded-full bg-gradient-to-tr from-blue-500 to-indigo-600 text-white flex items-center justify-center font-bold text-xs shadow-md shadow-blue-500/10">
                {(localStorage.getItem('username') || 'Op').substring(0, 2).toUpperCase()}
              </div>
              <button
                onClick={async () => {
                  await api.logout();
                  window.location.href = '/login';
                }}
                className="px-2.5 py-1 rounded-lg border border-rose-500/20 text-rose-500 bg-rose-500/5 hover:bg-rose-500/15 text-xs font-bold transition-all"
              >
                Logout
              </button>
            </div>
          </div>
        </header>

        {/* Content Viewport */}
        <main className="flex-1 p-8 overflow-y-auto">
          <ResourceContextMenu>
            <Outlet />
          </ResourceContextMenu>
        </main>

        {/* Spotlight Command Palette Modal */}
        <CommandPalette isOpen={cmdPaletteOpen} onClose={() => setCmdPaletteOpen(false)} />
      </div>
    </div>
  );
};

export default DashboardLayout;
