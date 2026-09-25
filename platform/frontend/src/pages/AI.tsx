import React, { useState, useEffect, useRef } from 'react';
import { api } from '../services/api';
import { AIResponse } from '../types';
import { Bot, Send, Sparkles, Trash2, RefreshCw, Layers, Shield, Server, FileText, CheckCircle2 } from 'lucide-react';
import { useScope } from '../context/ScopeContext';

interface ChatMessage {
  sender: 'user' | 'ai';
  text?: string;
  structured?: AIResponse;
  timestamp?: string;
}

const INITIAL_MESSAGE: ChatMessage = {
  sender: 'ai',
  text: '### 👋 DevOps Nexus AI Operations Assistant\n\nI am your infrastructure, log, and telemetry intelligence assistant. Ask me questions about:\n\n- 📊 **Cluster & Pod States:** Pod statuses, restart counts, node health, and replica counts.\n- 📜 **Log Analysis:** Error patterns, stack traces, and pod log streams.\n- 📈 **Telemetry Metrics:** CPU, memory, and network throughput.\n- 👥 **Identity & Security:** Users, roles, RBAC permissions matrix, and audit logs.\n- 🛡️ **Platform Operations:** Verification status and DevOps Nexus configurations.\n\n*Try asking:* "What is the current cluster health?", "How many pods are running?", "Show RBAC roles and permissions", or "Analyze system logs".',
  timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
};

const AI: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    try {
      const saved = localStorage.getItem('nexus_ai_chat_history');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch (e) {
      console.warn("Failed to load chat history:", e);
    }
    return [INITIAL_MESSAGE];
  });

  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [provider, setProvider] = useState('groq');
  const [progressStatus, setProgressStatus] = useState<string>('');
  
  const { getScopeParams, getScopeLabel } = useScope();
  const [sessionId] = useState(() => {
    let sid = localStorage.getItem('nexus_ai_session_id');
    if (!sid) {
      sid = 'session_' + Math.random().toString(36).substring(2, 10);
      localStorage.setItem('nexus_ai_session_id', sid);
    }
    return sid;
  });

  const chatEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    try {
      localStorage.setItem('nexus_ai_chat_history', JSON.stringify(messages));
    } catch (e) {
      console.warn("Failed to save chat history:", e);
    }
  }, [messages]);

  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, loading]);

  const handleSend = (text: string) => {
    if (!text.trim() || loading) return;

    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const userMsg: ChatMessage = { sender: 'user', text, timestamp: timeStr };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);
    setProgressStatus('Inspecting Cluster Metadata & Telemetry...');

    api.askAIStream(
      text,
      provider,
      sessionId,
      getScopeParams(),
      (status) => {
        setProgressStatus(status);
      },
      (data) => {
        const aiMsg: ChatMessage = {
          sender: 'ai',
          text: data.summary || data.root_cause,
          structured: data,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setMessages(prev => [...prev, aiMsg]);
        setLoading(false);
        setProgressStatus('');
      },
      (err) => {
        setMessages(prev => [...prev, { 
          sender: 'ai', 
          text: `### ⚠️ Connection Notice\n\n${err.message || 'Unable to reach AI completion endpoint.'}`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }]);
        setLoading(false);
        setProgressStatus('');
      }
    );
  };

  const handleClearHistory = () => {
    if (window.confirm("Are you sure you want to clear chat history and start a new session?")) {
      const newSid = 'session_' + Math.random().toString(36).substring(2, 10);
      localStorage.setItem('nexus_ai_session_id', newSid);
      setMessages([INITIAL_MESSAGE]);
      localStorage.removeItem('nexus_ai_chat_history');
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8.5rem)] space-y-4">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 bg-white dark:bg-slate-900 p-4 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-blue-600/10 border border-blue-500/20 flex items-center justify-center text-blue-500">
            <Bot className="h-6 w-6" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-800 dark:text-white flex items-center gap-2">
              AIOps Operations Assistant
              <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-blue-500/10 text-blue-500 border border-blue-500/20">
                {getScopeLabel()} Scope
              </span>
            </h2>
            <p className="text-xs text-slate-400">Context-aware infrastructure telemetry, pod logs, and metadata analysis.</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <label className="text-xs text-slate-400 font-semibold">Model Provider:</label>
            <select 
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="text-xs bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-white rounded-lg px-2.5 py-1.5 focus:outline-none"
            >
              <option value="groq">Groq (Llama 3.3 70B Versatile)</option>
              <option value="ollama">Ollama (Local Llama 3)</option>
              <option value="openai">OpenAI (GPT-4o-mini)</option>
            </select>
          </div>

          <button
            onClick={handleClearHistory}
            title="Clear Chat Session"
            className="p-2 rounded-xl bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-400 hover:text-rose-500 hover:border-rose-500/30 transition-all flex items-center gap-1.5 text-xs font-semibold"
          >
            <Trash2 className="h-3.5 w-3.5" />
            <span className="hidden md:inline">Clear Session</span>
          </button>
        </div>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-2">
        {messages.map((msg, idx) => (
          <div 
            key={idx} 
            className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div className={`max-w-3xl rounded-2xl p-5 border shadow-sm ${
              msg.sender === 'user' 
                ? 'bg-blue-600 text-white border-blue-500 shadow-blue-600/10' 
                : 'bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 text-slate-800 dark:text-white'
            }`}>
              <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-200/40 dark:border-slate-800">
                <span className="text-[11px] font-bold tracking-wide flex items-center gap-1.5">
                  {msg.sender === 'user' ? 'You' : (
                    <>
                      <Bot className="h-3.5 w-3.5 text-blue-500 inline" />
                      <span className="text-blue-500">DevOps Nexus AI Assistant</span>
                    </>
                  )}
                </span>
                {msg.timestamp && (
                  <span className="text-[10px] text-slate-400 font-mono">
                    {msg.timestamp}
                  </span>
                )}
              </div>

              {/* Message Content Render */}
              <div className="text-sm leading-relaxed whitespace-pre-wrap font-sans space-y-2">
                {msg.text || (msg.structured && (msg.structured.summary || msg.structured.root_cause))}
              </div>

              {/* Structured Telemetry Evidence Footer */}
              {msg.structured && msg.structured.evidence && msg.structured.evidence.length > 0 && (
                <div className="mt-4 pt-3 border-t border-slate-200 dark:border-slate-800 space-y-2">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                    <Sparkles className="h-3 w-3 text-blue-400" /> Grounded Evidence & State
                  </span>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                    {msg.structured.evidence.map((ev, i) => (
                      <div key={i} className="p-2 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200/60 dark:border-slate-700/60 text-slate-600 dark:text-slate-300 font-mono text-[11px]">
                        • {ev}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex items-center gap-2 text-xs text-blue-500 font-bold bg-blue-500/10 p-3.5 rounded-xl border border-blue-500/20 w-max shadow-sm animate-pulse">
            <Sparkles className="h-4 w-4 animate-spin" />
            <span>{progressStatus || 'Analyzing telemetry and cluster metadata...'}</span>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      {/* Input Box */}
      <div className="bg-white dark:bg-slate-900 p-3 rounded-2xl border border-slate-200 dark:border-slate-800 flex items-center gap-2 shadow-lg">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend(input)}
          placeholder="Ask AI Assistant about pod logs, cluster state, Prometheus metrics, users or roles..."
          className="flex-1 bg-transparent px-3 py-2 text-sm text-slate-800 dark:text-white placeholder-slate-400 focus:outline-none"
        />
        <button
          onClick={() => handleSend(input)}
          disabled={loading || !input.trim()}
          className="px-4 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 text-white font-bold text-xs flex items-center gap-2 transition-all cursor-pointer shadow-md shadow-blue-500/20"
        >
          <Send className="h-4 w-4" />
          Send
        </button>
      </div>
    </div>
  );
};

export default AI;
