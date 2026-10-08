import React, { useState, useEffect, useRef, useMemo } from 'react';
import { api } from '../services/api';
import { AIResponse } from '../types';
import { 
  Bot, Send, Sparkles, Trash2, Copy, Check, Terminal, 
  FastForward, ArrowRight, Zap 
} from 'lucide-react';
import { useScope } from '../context/ScopeContext';

interface ChatMessage {
  id: string;
  sender: 'user' | 'ai';
  text: string;
  displayedText?: string;
  isTyping?: boolean;
  isThinking?: boolean;
  structured?: AIResponse;
  timestamp?: string;
}

const INITIAL_ID = 'msg_initial';
const INITIAL_MESSAGE: ChatMessage = {
  id: INITIAL_ID,
  sender: 'ai',
  text: '### 👋 DevOps Nexus Live Kubernetes Assistant (Jarvis)\n\nI am your live cluster intelligence copilot powered by **Groq (Llama / GPT-OSS)**. I can analyze live telemetry, diagnose pod failures, suggest production-grade remediations, and explain complex Kubernetes architecture.\n\n- 📊 **Live Workloads & GitOps:** Pod statuses, restart counts, ArgoCD sync states, and node capacity.\n- 🔬 **Root Cause Analysis:** Container termination exit codes (OOMKilled 137, CrashLoopBackOff), probe failures, and Loki logs.\n- 🛠️ **Remediation Runbooks:** Actionable `kubectl` diagnostic commands, GitOps patch manifests, and rolling updates.\n- 🏛️ **Kubernetes Architecture:** Ingress vs Services, HPA/VPA/Karpenter autoscaling, StorageClasses, and RBAC matrix.\n\n*Try one of the suggested prompts below or ask any Kubernetes question!*',
  displayedText: '### 👋 DevOps Nexus Live Kubernetes Assistant (Jarvis)\n\nI am your live cluster intelligence copilot powered by **Groq (Llama / GPT-OSS)**. I can analyze live telemetry, diagnose pod failures, suggest production-grade remediations, and explain complex Kubernetes architecture.\n\n- 📊 **Live Workloads & GitOps:** Pod statuses, restart counts, ArgoCD sync states, and node capacity.\n- 🔬 **Root Cause Analysis:** Container termination exit codes (OOMKilled 137, CrashLoopBackOff), probe failures, and Loki logs.\n- 🛠️ **Remediation Runbooks:** Actionable `kubectl` diagnostic commands, GitOps patch manifests, and rolling updates.\n- 🏛️ **Kubernetes Architecture:** Ingress vs Services, HPA/VPA/Karpenter autoscaling, StorageClasses, and RBAC matrix.\n\n*Try one of the suggested prompts below or ask any Kubernetes question!*',
  isTyping: false,
  timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
};

const SUGGESTED_PROMPTS = [
  { label: "🐙 GitOps Pods", prompt: "How many pods are managed by GitOps?" },
  { label: "⚠️ Pod Restarts", prompt: "Which pod has the highest restarts and why?" },
  { label: "🛠️ Fix Restarts", prompt: "How do I fix payment-service restarts? Give me the yaml file" },
  { label: "⚖️ HPA Architecture", prompt: "Explain HPA and autoscaling in Kubernetes" },
  { label: "🌐 Ingress vs Service", prompt: "Explain Ingress vs Service types in Kubernetes" },
  { label: "🚨 Troubleshooting", prompt: "How do I troubleshoot a CrashLoopBackOff error?" },
  { label: "📈 Live Telemetry", prompt: "Show CPU and memory telemetry of the cluster" },
];

// --- Formatted Code Block Component ---
const CodeBlock: React.FC<{ language: string; code: string }> = ({ language, code }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="my-3 rounded-xl overflow-hidden border border-slate-700/70 bg-slate-950 shadow-md">
      <div className="flex items-center justify-between px-3.5 py-1.5 bg-slate-900 border-b border-slate-800 text-xs text-slate-400 font-mono">
        <span className="uppercase text-[11px] font-bold tracking-wider text-blue-400 flex items-center gap-1.5">
          <Terminal className="h-3 w-3" /> {language || 'code'}
        </span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-white transition-colors py-0.5 px-2 rounded bg-slate-800/80 hover:bg-slate-700"
          title="Copy code snippet"
        >
          {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
          <span>{copied ? 'Copied!' : 'Copy'}</span>
        </button>
      </div>
      <pre className="p-3.5 text-xs font-mono text-slate-200 overflow-x-auto leading-relaxed">
        <code>{code}</code>
      </pre>
    </div>
  );
};

// --- Formatted Table Component ---
const TableBlock: React.FC<{ rows: string[] }> = ({ rows }) => {
  if (rows.length < 2) {
    return <p className="text-xs font-mono text-slate-400 my-1">{rows[0]}</p>;
  }
  const parseRow = (rowStr: string) => {
    return rowStr.split('|').map(c => c.trim()).filter((_, i, arr) => i > 0 && i < arr.length - 1);
  };
  const headers = parseRow(rows[0]);
  const isSeparator = (r: string) => r.includes('---');
  const dataRows = rows.slice(1).filter(r => !isSeparator(r)).map(parseRow);

  return (
    <div className="my-3 overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
      <table className="w-full text-left text-xs border-collapse">
        <thead className="bg-slate-100 dark:bg-slate-800/80 text-slate-700 dark:text-slate-200 font-semibold border-b border-slate-200 dark:border-slate-700">
          <tr>
            {headers.map((h, i) => (
              <th key={i} className="p-2.5">
                <InlineFormatter text={h} />
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200 dark:divide-slate-800 font-sans">
          {dataRows.map((r, ri) => (
            <tr key={ri} className="even:bg-slate-50/50 dark:even:bg-slate-900/40 hover:bg-blue-50/30 dark:hover:bg-blue-900/10 transition-colors">
              {r.map((c, ci) => (
                <td key={ci} className="p-2.5 text-slate-600 dark:text-slate-300">
                  <InlineFormatter text={c} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

// --- Inline Formatter (Bold, Code spans, Italics) ---
const InlineFormatter: React.FC<{ text: string }> = ({ text }) => {
  const parts = useMemo(() => {
    const tokens: React.ReactNode[] = [];
    const regex = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g;
    let lastIndex = 0;
    let match;

    while ((match = regex.exec(text)) !== null) {
      if (match.index > lastIndex) {
        tokens.push(text.substring(lastIndex, match.index));
      }
      const token = match[0];
      if (token.startsWith('**') && token.endsWith('**')) {
        tokens.push(<strong key={match.index} className="font-bold text-slate-900 dark:text-white">{token.slice(2, -2)}</strong>);
      } else if (token.startsWith('`') && token.endsWith('`')) {
        tokens.push(
          <code key={match.index} className="font-mono text-[11px] bg-blue-500/10 text-blue-500 dark:text-blue-400 px-1.5 py-0.5 rounded border border-blue-500/20">
            {token.slice(1, -1)}
          </code>
        );
      } else if (token.startsWith('*') && token.endsWith('*')) {
        tokens.push(<em key={match.index} className="italic text-slate-600 dark:text-slate-300">{token.slice(1, -1)}</em>);
      }
      lastIndex = regex.lastIndex;
    }

    if (lastIndex < text.length) {
      tokens.push(text.substring(lastIndex));
    }
    return tokens;
  }, [text]);

  return <>{parts}</>;
};

// --- Comprehensive Markdown Block Renderer ---
const FormattedMarkdown: React.FC<{ content: string; isTyping?: boolean }> = ({ content, isTyping }) => {
  const elements = useMemo(() => {
    const lines = content.split('\n');
    const nodes: React.ReactNode[] = [];
    let i = 0;

    while (i < lines.length) {
      const line = lines[i];

      // Code Block
      if (line.trim().startsWith('```')) {
        const lang = line.trim().replace('```', '').trim();
        const codeLines: string[] = [];
        i++;
        while (i < lines.length && !lines[i].trim().startsWith('```')) {
          codeLines.push(lines[i]);
          i++;
        }
        nodes.push(<CodeBlock key={`code_${i}`} language={lang} code={codeLines.join('\n')} />);
        i++;
        continue;
      }

      // Markdown Table
      if (line.trim().startsWith('|') && line.trim().endsWith('|')) {
        const tableLines: string[] = [];
        while (i < lines.length && lines[i].trim().startsWith('|') && lines[i].trim().endsWith('|')) {
          tableLines.push(lines[i]);
          i++;
        }
        nodes.push(<TableBlock key={`table_${i}`} rows={tableLines} />);
        continue;
      }

      // Headings
      if (line.startsWith('### ')) {
        nodes.push(
          <h3 key={`h3_${i}`} className="text-base font-bold text-slate-800 dark:text-white mt-3 mb-1.5 flex items-center gap-1.5 border-b border-slate-200/50 dark:border-slate-800/80 pb-1">
            <InlineFormatter text={line.replace('### ', '')} />
          </h3>
        );
        i++;
        continue;
      }

      if (line.startsWith('#### ')) {
        nodes.push(
          <h4 key={`h4_${i}`} className="text-sm font-semibold text-slate-700 dark:text-slate-200 mt-2.5 mb-1">
            <InlineFormatter text={line.replace('#### ', '')} />
          </h4>
        );
        i++;
        continue;
      }

      // Blockquotes / Alerts
      if (line.startsWith('> ')) {
        nodes.push(
          <div key={`quote_${i}`} className="border-l-4 border-amber-500/80 bg-amber-500/10 px-3 py-2 rounded-r-lg text-xs text-slate-700 dark:text-slate-300 my-2">
            <InlineFormatter text={line.replace('> ', '')} />
          </div>
        );
        i++;
        continue;
      }

      // Lists
      if (line.trim().startsWith('- ') || line.trim().startsWith('* ')) {
        nodes.push(
          <div key={`li_${i}`} className="flex items-start gap-2 text-xs leading-relaxed text-slate-600 dark:text-slate-300 my-1 ml-1">
            <span className="text-blue-500 font-bold mt-0.5">•</span>
            <span><InlineFormatter text={line.trim().substring(2)} /></span>
          </div>
        );
        i++;
        continue;
      }

      // Regular Paragraphs
      if (line.trim()) {
        nodes.push(
          <p key={`p_${i}`} className="text-xs leading-relaxed text-slate-700 dark:text-slate-300 my-1.5">
            <InlineFormatter text={line} />
          </p>
        );
      }

      i++;
    }

    return nodes;
  }, [content]);

  return (
    <div className="space-y-0.5">
      {elements}
      {isTyping && (
        <span 
          aria-label="typing cursor" 
          className="inline-block w-2 h-4 ml-1 align-middle bg-blue-500 animate-pulse rounded-sm shadow-[0_0_8px_rgba(59,130,246,0.8)]" 
        />
      )}
    </div>
  );
};

// --- Self-Contained Fluid Typewriter Markdown Renderer ---
const TypewriterMarkdown: React.FC<{
  text: string;
  isTyping?: boolean;
  onTypingDone?: () => void;
}> = ({ text, isTyping, onTypingDone }) => {
  // If typing, initialize with at least 50 characters so the message starts rendering immediately!
  const [displayedLength, setDisplayedLength] = useState(() => (isTyping ? Math.min(50, text.length) : text.length));

  useEffect(() => {
    if (!isTyping) {
      setDisplayedLength(text.length);
      return;
    }

    if (displayedLength >= text.length) {
      onTypingDone?.();
      return;
    }

    // High-speed Claude/ChatGPT streaming pacing: ~45 to 140 chars per tick (~80fps) for fast responsive reading (<200ms)
    const step = Math.max(45, Math.min(140, Math.floor(text.length / 15)));
    const timer = setInterval(() => {
      setDisplayedLength((prev) => {
        const next = prev + step;
        if (next >= text.length) {
          clearInterval(timer);
          onTypingDone?.();
          return text.length;
        }
        return next;
      });
    }, 12);

    return () => clearInterval(timer);
  }, [isTyping, text, text.length, onTypingDone]);

  const currentContent = !isTyping ? text : text.slice(0, displayedLength);
  const stillTyping = !!isTyping && displayedLength < text.length;

  return <FormattedMarkdown content={currentContent} isTyping={stillTyping} />;
};

// --- Main AI Operations Component ---
const AI: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    try {
      const saved = localStorage.getItem('nexus_ai_chat_history');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) {
          // Remove any orphaned messages that have no text or were left in a thinking state
          const cleaned = parsed
            .filter((m: any) => m.sender === 'user' || (m.sender === 'ai' && m.text && m.text.trim()))
            .map((m: any) => ({
              ...m,
              isTyping: false,
              isThinking: false
            }));
          if (cleaned.length > 0) return cleaned;
        }
      }
    } catch (e) {
      console.warn("Failed to load chat history:", e);
    }
    return [INITIAL_MESSAGE];
  });

  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  // Model selection is advisory; the active provider/model is driven by the backend (AI_PROVIDER / LLM_MODEL).
  const [aiModel, setAiModel] = useState('openai/gpt-oss-120b');
  const [progressStatus, setProgressStatus] = useState<string>('');
  const [copiedMsgId, setCopiedMsgId] = useState<string | null>(null);

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

  // Sync completed messages to localStorage (excluding thinking or empty messages)
  useEffect(() => {
    try {
      const sanitized = messages
        .filter(m => !m.isThinking && (m.sender === 'user' ? m.text : (m.text && m.text.trim())))
        .map(m => ({
          ...m,
          isTyping: false,
          isThinking: false
        }));
      if (sanitized.length > 0) {
        localStorage.setItem('nexus_ai_chat_history', JSON.stringify(sanitized));
      }
    } catch (e) {
      console.warn("Failed to save chat history:", e);
    }
  }, [messages]);

  // Smooth Auto-scroll
  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, loading]);

  const handleFastForward = (msgId: string) => {
    setMessages(prev => prev.map(m => {
      if (m.id === msgId) {
        return { ...m, isTyping: false };
      }
      return m;
    }));
  };

  const handleTypingDone = (msgId: string) => {
    setMessages(prev => prev.map(m => {
      if (m.id === msgId) {
        return { ...m, isTyping: false };
      }
      return m;
    }));
  };

  const handleCopyMessage = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedMsgId(id);
    setTimeout(() => setCopiedMsgId(null), 2000);
  };

  const handleSend = (text: string) => {
    if (!text.trim() || loading) return;

    // Fast-forward any active typing before sending new message
    setMessages(prev => prev.map(m => m.isTyping ? { ...m, isTyping: false } : m));

    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const userMsg: ChatMessage = {
      id: 'msg_user_' + Date.now(),
      sender: 'user',
      text,
      timestamp: timeStr
    };
    const pendingAiId = 'msg_ai_' + (Date.now() + 1);
    const pendingAiMsg: ChatMessage = {
      id: pendingAiId,
      sender: 'ai',
      text: '',
      isThinking: true,
      timestamp: timeStr
    };
    setMessages(prev => [...prev, userMsg, pendingAiMsg]);
    setInput('');
    setLoading(true);
    setProgressStatus('Inspecting Live Cluster Telemetry...');

    let isDone = false;
    const safetyTimeout = setTimeout(() => {
      if (!isDone) {
        isDone = true;
        setMessages(prev => prev.map(m => {
          if (m.id === pendingAiId && m.isThinking) {
            return {
              ...m,
              text: '### ⚠️ Response Notice\n\nThe diagnostic query took longer than expected. Please verify backend connectivity.',
              isThinking: false,
              isTyping: false,
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            };
          }
          return m;
        }));
        setLoading(false);
        setProgressStatus('');
      }
    }, 60000);

    api.askAIStream(
      text,
      'groq',
      sessionId,
      getScopeParams(),
      (status) => {
        if (!isDone) setProgressStatus(status);
      },
      (data) => {
        if (isDone) return;
        isDone = true;
        clearTimeout(safetyTimeout);
        const fullResponse = data.summary || data.root_cause || 'AI operations analysis completed.';
        setMessages(prev => prev.map(m => {
          if (m.id === pendingAiId) {
            return {
              ...m,
              text: fullResponse,
              isThinking: false,
              isTyping: false,
              structured: data,
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            };
          }
          return m;
        }));
        setLoading(false);
        setProgressStatus('');
      },
      (err) => {
        if (isDone) return;
        isDone = true;
        clearTimeout(safetyTimeout);
        const errNotice = `### ⚠️ Connection Notice\n\n${err.message || 'Unable to reach AI completion endpoint.'}`;
        setMessages(prev => prev.map(m => {
          if (m.id === pendingAiId) {
            return {
              ...m,
              text: errNotice,
              isThinking: false,
              isTyping: false,
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            };
          }
          return m;
        }));
        setLoading(false);
        setProgressStatus('');
      },
      aiModel
    );
  };

  const handleClearHistory = () => {
    if (window.confirm("Are you sure you want to clear chat history and start a fresh session?")) {
      const newSid = 'session_' + Math.random().toString(36).substring(2, 10);
      localStorage.setItem('nexus_ai_session_id', newSid);
      setMessages([INITIAL_MESSAGE]);
      localStorage.removeItem('nexus_ai_chat_history');
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8.5rem)] space-y-3 font-sans">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 bg-white dark:bg-slate-900 p-4 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-500 shadow-sm">
            <Bot className="h-6 w-6" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-800 dark:text-white flex items-center gap-2">
              DevOps Nexus Live Kubernetes Assistant
              <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-amber-500/10 text-amber-500 border border-amber-500/20">
                Groq Jarvis
              </span>
              <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-blue-500/10 text-blue-500 border border-blue-500/20">
                {getScopeLabel()} Scope
              </span>
            </h2>
            <p className="text-xs text-slate-400">Conversational SRE Intelligence grounded in live Amazon EKS cluster telemetry and GitOps state.</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <label className="text-xs text-slate-400 font-semibold">Groq Model:</label>
            <select 
              value={aiModel}
              onChange={(e) => setAiModel(e.target.value)}
              className="text-xs bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-white rounded-lg px-2.5 py-1.5 focus:outline-none font-medium cursor-pointer"
            >
              <option value="openai/gpt-oss-120b">GPT-OSS 120B (quality)</option>
              <option value="openai/gpt-oss-20b">GPT-OSS 20B (fast)</option>
              <option value="qwen/qwen3.8-27b">Qwen 3 27B</option>
            </select>
          </div>

          <button
            onClick={handleClearHistory}
            title="Clear Chat Session"
            className="p-2 rounded-xl bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-400 hover:text-rose-500 hover:border-rose-500/30 transition-all flex items-center gap-1.5 text-xs font-semibold cursor-pointer"
          >
            <Trash2 className="h-3.5 w-3.5" />
            <span className="hidden md:inline">Clear Session</span>
          </button>
        </div>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-2">
        {messages.map((msg) => (
          <div 
            key={msg.id} 
            className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div className={`max-w-3xl rounded-2xl p-5 border shadow-sm transition-all ${
              msg.sender === 'user' 
                ? 'bg-blue-600 text-white border-blue-500 shadow-blue-600/10' 
                : 'bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 text-slate-800 dark:text-white'
            }`}>
              {/* Message Header Bar */}
              <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-200/40 dark:border-slate-800">
                <span className="text-[11px] font-bold tracking-wide flex items-center gap-1.5">
                  {msg.sender === 'user' ? (
                    'You'
                  ) : (
                    <>
                      <Bot className="h-3.5 w-3.5 text-blue-500 inline" />
                      <span className="text-blue-500">Nexus Jarvis (K8s Copilot)</span>
                    </>
                  )}
                </span>
                <div className="flex items-center gap-2">
                  {msg.sender === 'ai' && (
                    <button
                      onClick={() => handleCopyMessage(msg.id, msg.text)}
                      className="text-slate-400 hover:text-slate-200 transition-colors flex items-center gap-1 text-[11px] px-1.5 py-0.5 rounded hover:bg-slate-800 cursor-pointer"
                      title="Copy response"
                    >
                      {copiedMsgId === msg.id ? (
                        <>
                          <Check className="h-3 w-3 text-emerald-400" />
                          <span className="text-[10px] text-emerald-400">Copied</span>
                        </>
                      ) : (
                        <>
                          <Copy className="h-3 w-3" />
                          <span className="text-[10px]">Copy</span>
                        </>
                      )}
                    </button>
                  )}
                  {msg.timestamp && (
                    <span className="text-[10px] text-slate-400 font-mono">
                      {msg.timestamp}
                    </span>
                  )}
                </div>
              </div>

              {/* Message Content Render */}
              <div className="text-xs leading-relaxed font-sans">
                {msg.sender === 'user' ? (
                  <div className="whitespace-pre-wrap">{msg.text}</div>
                ) : msg.isThinking ? (
                  <div className="flex items-center gap-3 py-2.5 text-slate-500 dark:text-slate-400">
                    <div className="flex items-center gap-1.5">
                      <span className="h-2.5 w-2.5 rounded-full bg-blue-500 animate-bounce" style={{ animationDelay: '0ms' }} />
                      <span className="h-2.5 w-2.5 rounded-full bg-blue-500 animate-bounce" style={{ animationDelay: '150ms' }} />
                      <span className="h-2.5 w-2.5 rounded-full bg-blue-500 animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                    <span className="text-xs font-semibold text-slate-700 dark:text-slate-200 tracking-wide">
                      {progressStatus || 'Inspecting live cluster telemetry & workloads...'}
                    </span>
                  </div>
                ) : (
                  <TypewriterMarkdown 
                    text={msg.text} 
                    isTyping={msg.isTyping} 
                    onTypingDone={() => handleTypingDone(msg.id)} 
                  />
                )}
              </div>

              {/* Fast-Forward Button when typing */}
              {msg.isTyping && (
                <div className="mt-3 pt-2 border-t border-slate-200/40 dark:border-slate-800 flex items-center justify-between">
                  <span className="text-[10px] text-blue-400 flex items-center gap-1 font-medium">
                    <Sparkles className="h-3 w-3 animate-spin text-blue-400" /> Typing response...
                  </span>
                  <button
                    onClick={() => handleFastForward(msg.id)}
                    className="flex items-center gap-1 text-[11px] text-blue-400 hover:text-blue-300 font-semibold bg-blue-500/10 hover:bg-blue-500/20 px-2 py-0.5 rounded-lg border border-blue-500/20 transition-all cursor-pointer"
                    title="Skip typing and display full answer"
                  >
                    <FastForward className="h-3 w-3" /> Fast-Forward
                  </button>
                </div>
              )}

              {/* Structured Telemetry Evidence Footer */}
              {!msg.isTyping && !msg.isThinking && msg.structured && msg.structured.evidence && msg.structured.evidence.length > 0 && (
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

        <div ref={chatEndRef} />
      </div>

      {/* Suggested Follow-Up Prompt Pills */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 pt-1 no-scrollbar">
        <span className="text-[11px] font-bold text-slate-400 whitespace-nowrap flex items-center gap-1">
          <Zap className="h-3 w-3 text-amber-500" /> Quick Prompts:
        </span>
        {SUGGESTED_PROMPTS.map((item, idx) => (
          <button
            key={idx}
            onClick={() => handleSend(item.prompt)}
            disabled={loading}
            className="text-xs whitespace-nowrap px-3 py-1.5 rounded-full bg-slate-100 hover:bg-blue-50 dark:bg-slate-800/90 dark:hover:bg-blue-900/30 text-slate-700 dark:text-slate-300 hover:text-blue-600 dark:hover:text-blue-400 border border-slate-200/80 dark:border-slate-700 transition-all font-medium flex items-center gap-1.5 shadow-sm cursor-pointer disabled:opacity-50"
          >
            <span>{item.label}</span>
            <ArrowRight className="h-3 w-3 opacity-60" />
          </button>
        ))}
      </div>

      {/* Input Box */}
      <div className="bg-white dark:bg-slate-900 p-3 rounded-2xl border border-slate-200 dark:border-slate-800 flex items-center gap-2 shadow-lg">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend(input)}
          placeholder="Ask Jarvis about pod errors, CrashLoopBackOff fixes, HPA, YAML manifests, or live telemetry..."
          className="flex-1 bg-transparent px-3 py-2 text-xs sm:text-sm text-slate-800 dark:text-white placeholder-slate-400 focus:outline-none"
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
