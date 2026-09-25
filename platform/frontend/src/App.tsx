import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import DashboardLayout from './layouts/DashboardLayout';
import Overview from './pages/Overview';
import Deployments from './pages/Deployments';
import Pods from './pages/Pods';
import Nodes from './pages/Nodes';
import Namespaces from './pages/Namespaces';
import Metrics from './pages/Metrics';
import Logs from './pages/Logs';
import Alerts from './pages/Alerts';
import AI from './pages/AI';
import Settings from './pages/Settings';
import Login from './pages/Login';
import { ForcePasswordChange } from './pages/ForcePasswordChange';
import NotFound from './pages/NotFound';
import ProtectedRoute from './components/ProtectedRoute';
import { ScopeProvider } from './context/ScopeContext';
import { ClusterProvider } from './context/ClusterContext';
import { Clusters } from './pages/Clusters';

import { UsersPage } from './pages/admin/Users';
import { RolesPage } from './pages/admin/Roles';
import { PermissionsMatrixPage } from './pages/admin/PermissionsMatrix';
import { AuditLogsPage } from './pages/admin/AuditLogs';
import { VerificationDashboardPage } from './pages/admin/VerificationDashboard';
import { AWSAccountsPage } from './pages/AWSAccounts';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public Login & Password Change Routes */}
        <Route path="/login" element={<Login />} />
        <Route 
          path="/force-password-change" 
          element={
            <ProtectedRoute>
              <ForcePasswordChange />
            </ProtectedRoute>
          } 
        />

        {/* Protected Dashboard Views */}
        <Route 
          path="/" 
          element={
            <ProtectedRoute>
              <ClusterProvider>
                <ScopeProvider>
                  <DashboardLayout />
                </ScopeProvider>
              </ClusterProvider>
            </ProtectedRoute>
          } 
        >
          <Route index element={<Navigate to="/overview" replace />} />
          <Route path="overview" element={<Overview />} />
          <Route path="clusters" element={<Clusters />} />
          <Route 
            path="aws/accounts" 
            element={
              <ProtectedRoute allowedRoles={['Administrator', 'Platform Engineer', 'DevOps Engineer']}>
                <AWSAccountsPage />
              </ProtectedRoute>
            } 
          />
          <Route path="metrics" element={<Metrics />} />
          <Route path="ai" element={<AI />} />
          
          <Route 
            path="deployments" 
            element={
              <ProtectedRoute allowedRoles={['Administrator', 'Platform Engineer', 'DevOps Engineer', 'Developer']}>
                <Deployments />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="logs" 
            element={
              <ProtectedRoute allowedRoles={['Administrator', 'Platform Engineer', 'DevOps Engineer', 'Developer']}>
                <Logs />
              </ProtectedRoute>
            } 
          />
          
          <Route 
            path="pods" 
            element={
              <ProtectedRoute allowedRoles={['Administrator', 'Platform Engineer', 'DevOps Engineer']}>
                <Pods />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="nodes" 
            element={
              <ProtectedRoute allowedRoles={['Administrator', 'Platform Engineer', 'DevOps Engineer']}>
                <Nodes />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="namespaces" 
            element={
              <ProtectedRoute allowedRoles={['Administrator', 'Platform Engineer', 'DevOps Engineer']}>
                <Namespaces />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="alerts" 
            element={
              <ProtectedRoute allowedRoles={['Administrator', 'Platform Engineer', 'DevOps Engineer']}>
                <Alerts />
              </ProtectedRoute>
            } 
          />
          
          {/* Admin Protected EWRAM Pages (Administrator & Platform Engineer Only) */}
          <Route 
            path="admin/users" 
            element={
              <ProtectedRoute allowedRoles={['Administrator', 'Platform Engineer']}>
                <UsersPage />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="admin/roles" 
            element={
              <ProtectedRoute allowedRoles={['Administrator', 'Platform Engineer']}>
                <RolesPage />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="admin/permissions" 
            element={
              <ProtectedRoute allowedRoles={['Administrator', 'Platform Engineer']}>
                <PermissionsMatrixPage />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="admin/audit" 
            element={
              <ProtectedRoute allowedRoles={['Administrator', 'Platform Engineer']}>
                <AuditLogsPage />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="admin/verification" 
            element={
              <ProtectedRoute allowedRoles={['Administrator', 'Platform Engineer']}>
                <VerificationDashboardPage />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="settings" 
            element={
              <ProtectedRoute allowedRoles={['Administrator', 'Platform Engineer']}>
                <Settings />
              </ProtectedRoute>
            } 
          />
          
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
