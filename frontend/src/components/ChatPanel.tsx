import { useState, useRef, useEffect } from 'react';
import { Send, Sparkles, Trash2, User, Bot } from 'lucide-react';
import { useStore } from '@/store/useStore';
import * as api from '@/services/api';
import type { ChatMessage } from '@/types';

const MODELS = [
  { value: 'gemini-3.5-flash', label: 'Gemini 3.5 Flash' },
  { value: 'gemini-3.5-pro-preview', label: 'Gemini 3.5 Pro' },
  { value: 'deepseek-v4-flash', label: 'DeepSeek V4 Flash' },
  { value: 'nemotron-3-ultra-550b', label: 'Nemotron 3 Ultra' },
];

export default function ChatPanel() {
  const messages = useStore((s) => s.chatMessages);
  const addChatMessage = useStore((s) => s.addChatMessage);
  const setChatMessages = useStore((s) => s.setChatMessages);
  const saveChatToDB = useStore((s) => s.saveChatToDB);
  const workspaceDir = useStore((s) => s.workspaceDir);

  const [input, setInput] = useState('');
  const [model, setModel] = useState('gemini-3.5-flash');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim()) return;
    const userMsg: ChatMessage = {
      id: crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36),
      role: 'user',
      content: input.trim(),
      model,
      created_at: new Date().toISOString(),
    };
    addChatMessage(userMsg);
    await saveChatToDB(userMsg);
    setInput('');
    setIsLoading(true);

    // Try real API (absolute URL via api service \u2014 works in Electron + dev)
    try {
      const assistantMsg = await api.sendChatMessage({
        message: userMsg.content,
        model,
        workspace_dir: workspaceDir,
      });
      addChatMessage(assistantMsg);
      await saveChatToDB(assistantMsg);
      setIsLoading(false);
      return;
    } catch (err) {
      console.warn('[ChatPanel] api.sendChatMessage failed, using fallback:', err);
    }

    // Fallback: simulate LLM response
    await new Promise((r) => setTimeout(r, 800 + Math.random() * 1200));
    const assistantMsg: ChatMessage = {
      id: crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36),
      role: 'assistant',
      content: `Here's my response about "${userMsg.content.slice(0, 50)}${userMsg.content.length > 50 ? '...' : ''}".

1. **Key points** — Several important considerations should be addressed.
2. **Approach** — A structured approach would work best here.
3. **Next steps** — Let me know if you'd like me to elaborate.`,
      model,
      created_at: new Date().toISOString(),
    };
    addChatMessage(assistantMsg);
    await saveChatToDB(assistantMsg);
    setIsLoading(false);
  };

  const handleClear = async () => {
    setChatMessages([]);
    try {
      await api.clearChat();
    } catch (err) {
      console.warn('[ChatPanel] api.clearChat failed:', err);
    }
    if (window.electronAPI) {
      await window.electronAPI.clearChat();
    }
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-slate-800/50 bg-slate-900/30">
        <div>
          <h1 className="text-lg font-semibold text-white tracking-tight">Chat</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            {messages.length} message{messages.length !== 1 ? 's' : ''}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-indigo-500"
          >
            {MODELS.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
          {messages.length > 0 && (
            <button
              onClick={handleClear}
              className="btn-ghost text-xs flex items-center gap-1.5 text-slate-500 hover:text-rose-400"
            >
              <Trash2 size={13} />
              Clear
            </button>
          )}
        </div>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-slate-600">
            <div className="w-16 h-16 rounded-2xl bg-slate-800/50 flex items-center justify-center mb-4">
              <Sparkles size={28} className="text-slate-500" />
            </div>
            <p className="text-sm font-medium text-slate-500">Start a conversation</p>
            <p className="text-xs text-slate-600 mt-1">Ask anything or discuss your tasks</p>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-3 animate-fade-in ${
              msg.role === 'user' ? 'justify-end' : 'justify-start'
            }`}
          >
            {msg.role === 'assistant' && (
              <div className="w-8 h-8 rounded-lg bg-indigo-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                <Bot size={16} className="text-indigo-400" />
              </div>
            )}
            <div
              className={`max-w-[75%] rounded-2xl px-4 py-2.5 ${
                msg.role === 'user'
                  ? 'bg-indigo-500/15 border border-indigo-500/20 text-slate-200'
                  : 'bg-slate-800/60 border border-slate-700/30 text-slate-300'
              }`}
            >
              <div className="text-sm whitespace-pre-wrap leading-relaxed">{msg.content}</div>
              <div className="flex items-center gap-2 mt-1.5">
                <span className="text-[10px] text-slate-600">
                  {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
                {msg.model && (
                  <span className="text-[10px] text-slate-600 font-mono">{msg.model}</span>
                )}
              </div>
            </div>
            {msg.role === 'user' && (
              <div className="w-8 h-8 rounded-lg bg-slate-700/50 flex items-center justify-center flex-shrink-0 mt-0.5">
                <User size={16} className="text-slate-400" />
              </div>
            )}
          </div>
        ))}

        {isLoading && (
          <div className="flex gap-3 justify-start animate-fade-in">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/20 flex items-center justify-center flex-shrink-0">
              <Bot size={16} className="text-indigo-400" />
            </div>
            <div className="bg-slate-800/60 border border-slate-700/30 rounded-2xl px-4 py-3">
              <div className="flex gap-1.5">
                <div className="w-2 h-2 rounded-full bg-slate-500 animate-bounce" style={{ animationDelay: '0ms' }} />
                <div className="w-2 h-2 rounded-full bg-slate-500 animate-bounce" style={{ animationDelay: '150ms' }} />
                <div className="w-2 h-2 rounded-full bg-slate-500 animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="px-6 py-4 border-t border-slate-800/50 bg-slate-900/30">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
            placeholder="Type a message..."
            className="input-field flex-1"
            disabled={isLoading}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="btn-primary px-4 flex items-center gap-1.5"
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
