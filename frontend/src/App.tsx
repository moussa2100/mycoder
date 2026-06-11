import { useEffect, useState } from 'react';
import { useStore } from '@/store/useStore';
import { FolderOpen, CheckCircle2, AlertCircle } from 'lucide-react';
import * as api from '@/services/api';
import Sidebar from '@/components/Sidebar';
import KanbanBoard from '@/components/KanbanBoard';
import ChatPanel from '@/components/ChatPanel';
import CreateTaskModal from '@/components/CreateTaskModal';
import TaskDetailModal from '@/components/TaskDetailModal';

export default function App() {
  const view = useStore((s) => s.view);
  const checkBackendHealth = useStore((s) => s.checkBackendHealth);
  const loadFromAPI = useStore((s) => s.loadFromAPI);
  const loadChatFromAPI = useStore((s) => s.loadChatFromAPI);
  const workspaceDir = useStore((s) => s.workspaceDir);
  const setWorkspaceDir = useStore((s) => s.setWorkspaceDir);
  const isBackendAvailable = useStore((s) => s.isBackendAvailable);

  const [dirInput, setDirInput] = useState(workspaceDir);
  const [wsValid, setWsValid] = useState<'valid' | 'invalid' | null>(null);

  useEffect(() => {
    setDirInput(workspaceDir);
  }, [workspaceDir]);

  useEffect(() => {
    window.electronAPI?.getWorkspace?.().then((dir) => {
      if (dir) setWorkspaceDir(dir);
    });

    checkBackendHealth().then(() => {
      loadFromAPI();
      loadChatFromAPI();
    });
  }, []);

  const handleDirSubmit = async () => {
    const trimmed = dirInput.trim();
    if (!trimmed) return;

    try {
      const info = await api.validateWorkspace(trimmed);
      if (info.exists && info.is_directory) {
        setWorkspaceDir(info.path);
        setWsValid('valid');
        setTimeout(() => setWsValid(null), 2000);
      } else {
        setWsValid('invalid');
        setTimeout(() => setWsValid(null), 3000);
      }
    } catch {
      // If backend not available, still set the path for local use
      setWorkspaceDir(trimmed);
      setWsValid('valid');
      setTimeout(() => setWsValid(null), 2000);
    }
  };

  const handleBrowse = async () => {
    if (!window.electronAPI?.selectWorkspace) return;
    const dir = await window.electronAPI.selectWorkspace();
    if (!dir) return;
    setDirInput(dir);
    setWorkspaceDir(dir);
    setWsValid('valid');
    setTimeout(() => setWsValid(null), 2000);
  };

  const isElectron = typeof window !== 'undefined' && !!window.electronAPI;

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-950">
      <Sidebar />
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Workspace Bar */}
        <div className="flex items-center gap-3 px-4 py-2 border-b border-slate-800/50 bg-slate-900/40">
          <FolderOpen size={16} className="text-slate-500 flex-shrink-0" />
          <input
            type="text"
            value={dirInput}
            onChange={(e) => setDirInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleDirSubmit()}
            placeholder="Working directory path..."
            className="flex-1 bg-slate-800/50 border border-slate-700/50 rounded-lg px-3 py-1.5 text-sm text-slate-300 placeholder:text-slate-600 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 transition-all"
          />
          {isElectron && (
            <button
              onClick={handleBrowse}
              className="px-3 py-1.5 rounded-lg bg-slate-800/60 border border-slate-700/50 text-slate-300 text-xs font-medium hover:bg-slate-700/60 transition-all flex items-center gap-1.5"
              title="Browse for a folder"
            >
              <FolderOpen size={12} /> Browse…
            </button>
          )}
          <button
            onClick={handleDirSubmit}
            className="px-3 py-1.5 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-medium hover:bg-indigo-500/20 transition-all"
          >
            Set
          </button>
          {wsValid === 'valid' && (
            <CheckCircle2 size={16} className="text-emerald-400 flex-shrink-0" />
          )}
          {wsValid === 'invalid' && (
            <div className="flex items-center gap-1 text-amber-400 text-xs flex-shrink-0">
              <AlertCircle size={14} />
              Invalid path
            </div>
          )}
          {/* Backend status indicator */}
          <div className="flex items-center gap-1.5 text-xs flex-shrink-0 ml-2">
            <div className={`w-1.5 h-1.5 rounded-full ${isBackendAvailable ? 'bg-emerald-400' : 'bg-slate-600'}`} />
            <span className={isBackendAvailable ? 'text-emerald-400' : 'text-slate-600'}>
              {isBackendAvailable ? 'API' : 'Offline'}
            </span>
          </div>
        </div>
        {view === 'kanban' ? <KanbanBoard /> : <ChatPanel />}
      </main>
      <CreateTaskModal />
      <TaskDetailModal />
    </div>
  );
}
