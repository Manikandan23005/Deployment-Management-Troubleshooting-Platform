import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import { TerminalSquare, ShieldAlert, KeyRound, User } from 'lucide-react';

const Login: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const data = await api.login(username, password);
      if (data?.require_password_change) {
        navigate('/force-password-change');
      } else {
        navigate('/overview');
      }
    } catch (err: any) {
      setError(err.message || 'Authentication failed. Please verify credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0b0f19] px-4 font-sans select-none relative overflow-hidden">
      {/* Dynamic Background Glows */}
      <div className="absolute top-[-20%] left-[-10%] h-[600px] w-[600px] bg-blue-600/10 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-20%] right-[-10%] h-[600px] w-[600px] bg-indigo-600/10 rounded-full blur-[120px] pointer-events-none" />

      {/* Main Glassmorphic Login Container */}
      <div className="w-full max-w-md glass-panel p-8 rounded-3xl border border-slate-800 bg-slate-900/60 backdrop-blur-xl shadow-2xl relative z-10 space-y-8">
        
        {/* Logo and Branding Header */}
        <div className="flex flex-col items-center text-center space-y-3">
          <div className="h-14 w-14 rounded-2xl bg-blue-600/15 border border-blue-500/30 flex items-center justify-center text-blue-500 shadow-lg shadow-blue-500/5">
            <TerminalSquare className="h-8 w-8" />
          </div>
          <div className="space-y-1">
            <h1 className="text-2xl font-bold text-white tracking-wide bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">
              DevOps Nexus
            </h1>
            <p className="text-xs text-slate-400 font-medium">Unified Operations & AIOps Platform</p>
          </div>
        </div>

        {/* Error Alert Display */}
        {error && (
          <div className="flex items-center gap-3 p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs">
            <ShieldAlert className="h-5 w-5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Input Form */}
        <form onSubmit={handleLogin} className="space-y-5">
          {/* Username Field */}
          <div className="space-y-1.5">
            <label className="text-xs text-slate-400 font-semibold block">Username</label>
            <div className="relative">
              <span className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500">
                <User className="h-4.5 w-4.5" />
              </span>
              <input 
                type="text" 
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter operator username"
                required
                className="w-full pl-11 pr-4 py-3 rounded-xl bg-slate-950/80 border border-slate-800 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500 transition-all"
              />
            </div>
          </div>

          {/* Password Field */}
          <div className="space-y-1.5">
            <label className="text-xs text-slate-400 font-semibold block">Password</label>
            <div className="relative">
              <span className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500">
                <KeyRound className="h-4.5 w-4.5" />
              </span>
              <input 
                type="password" 
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                className="w-full pl-11 pr-4 py-3 rounded-xl bg-slate-950/80 border border-slate-800 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500 transition-all"
              />
            </div>
          </div>

          {/* Submit Button */}
          <button 
            type="submit"
            disabled={loading}
            className="w-full py-3.5 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:bg-blue-800 text-sm font-bold text-white shadow-lg shadow-blue-500/20 active:scale-[0.98] transition-all cursor-pointer"
          >
            {loading ? 'Authenticating Operator...' : 'Authorize Session'}
          </button>

          {/* Quick-fill Demo Credentials */}
          <div className="pt-2 text-center border-t border-slate-800/60">
            <p className="text-[11px] text-slate-500 font-medium">
              Default operator:{' '}
              <button
                type="button"
                onClick={() => {
                  setUsername('admin');
                  setPassword('DevOpsNexus@123');
                }}
                className="text-blue-400 hover:text-blue-300 font-mono underline cursor-pointer"
              >
                admin / DevOpsNexus@123
              </button>
            </p>
          </div>
        </form>
      </div>
    </div>
  );
};

export default Login;
