import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import { ShieldAlert, KeyRound, Lock, CheckCircle2 } from 'lucide-react';

export const ForcePasswordChange: React.FC = () => {
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (newPassword.length < 6) {
      setError('New password must be at least 6 characters long.');
      return;
    }

    if (newPassword !== confirmPassword) {
      setError('New password and confirmation password do not match.');
      return;
    }

    setLoading(true);
    try {
      await api.changePassword(oldPassword, newPassword);
      alert('Password updated successfully! Welcome to DevOps Nexus.');
      navigate('/overview');
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to update password. Please check your current password.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0b0f19] px-4 font-sans select-none relative overflow-hidden">
      {/* Background Glows */}
      <div className="absolute top-[-20%] left-[-10%] h-[600px] w-[600px] bg-amber-600/10 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-20%] right-[-10%] h-[600px] w-[600px] bg-blue-600/10 rounded-full blur-[120px] pointer-events-none" />

      <div className="w-full max-w-md p-8 rounded-3xl border border-slate-800 bg-slate-900/70 backdrop-blur-xl shadow-2xl relative z-10 space-y-6">
        
        {/* Warning Icon & Header */}
        <div className="flex flex-col items-center text-center space-y-3">
          <div className="h-14 w-14 rounded-2xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-500 shadow-lg shadow-amber-500/5">
            <Lock className="h-8 w-8" />
          </div>
          <div className="space-y-1">
            <h2 className="text-2xl font-bold text-white tracking-wide">First Login Password Change</h2>
            <p className="text-xs text-slate-400">Security Policy: Default & temporary passwords must be updated before accessing the platform dashboard.</p>
          </div>
        </div>

        {/* Error Alert Display */}
        {error && (
          <div className="flex items-center gap-3 p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs">
            <ShieldAlert className="h-5 w-5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4 text-sm">
          <div>
            <label className="text-xs text-slate-400 font-semibold block mb-1">Current / Default Password</label>
            <div className="relative">
              <span className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500">
                <KeyRound className="h-4 w-4" />
              </span>
              <input
                type="password"
                required
                value={oldPassword}
                onChange={(e) => setOldPassword(e.target.value)}
                placeholder="Enter current password"
                className="w-full pl-11 pr-4 py-3 rounded-xl bg-slate-950/80 border border-slate-800 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-amber-500 transition-all"
              />
            </div>
          </div>

          <div>
            <label className="text-xs text-slate-400 font-semibold block mb-1">New Password</label>
            <div className="relative">
              <span className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500">
                <Lock className="h-4 w-4" />
              </span>
              <input
                type="password"
                required
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Enter strong new password"
                className="w-full pl-11 pr-4 py-3 rounded-xl bg-slate-950/80 border border-slate-800 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-amber-500 transition-all"
              />
            </div>
          </div>

          <div>
            <label className="text-xs text-slate-400 font-semibold block mb-1">Confirm New Password</label>
            <div className="relative">
              <span className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500">
                <CheckCircle2 className="h-4 w-4" />
              </span>
              <input
                type="password"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Re-enter new password"
                className="w-full pl-11 pr-4 py-3 rounded-xl bg-slate-950/80 border border-slate-800 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-amber-500 transition-all"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3.5 rounded-xl bg-amber-600 hover:bg-amber-500 disabled:bg-amber-800 text-sm font-bold text-white shadow-lg shadow-amber-500/20 active:scale-[0.98] transition-all cursor-pointer mt-2"
          >
            {loading ? 'Updating Password...' : 'Update Password & Continue'}
          </button>
        </form>
      </div>
    </div>
  );
};
