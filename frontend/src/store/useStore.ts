import { create } from 'zustand';
import type { Task, TaskStatus, ChatMessage, ViewType } from '@/types';
import * as api from '@/services/api';

function genId(): string {
  return crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2);
}

interface AppState {
  // Navigation
  view: ViewType;
  setView: (v: ViewType) => void;

  // Workspace
  workspaceDir: string;
  setWorkspaceDir: (dir: string) => void;

  // API availability
  isBackendAvailable: boolean;
  setBackendAvailable: (v: boolean) => void;

  // Tasks
  tasks: Task[];
  setTasks: (tasks: Task[]) => void;
  addTask: (task: Task) => void;
  updateTask: (task: Task) => void;
  removeTask: (id: string) => void;

  // Modals
  showCreateModal: boolean;
  openCreateModal: () => void;
  closeCreateModal: () => void;
  selectedTaskId: string | null;
  detailTask: Task | null;
  openTaskDetail: (task: Task) => void;
  closeTaskDetail: () => void;

  // Create form state
  newTaskTitle: string;
  newTaskDescription: string;
  selectedModel: string;
  llmPlan: string;
  isGeneratingPlan: boolean;
  planConversation: string;
  setNewTaskTitle: (v: string) => void;
  setNewTaskDescription: (v: string) => void;
  setSelectedModel: (v: string) => void;
  setLlmPlan: (v: string) => void;
  setIsGeneratingPlan: (v: boolean) => void;
  setPlanConversation: (v: string) => void;

  // Chat
  chatMessages: ChatMessage[];
  setChatMessages: (msgs: ChatMessage[]) => void;
  addChatMessage: (msg: ChatMessage) => void;

  // Streaming
  streamingContent: string;
  setStreamingContent: (v: string) => void;
  appendStreamingContent: (v: string) => void;
  stopStreaming: (() => void) | null;
  setStopStreaming: (fn: (() => void) | null) => void;

  // DB sync helpers (fallback to Electron IPC)
  loadFromDB: () => Promise<void>;
  saveTaskToDB: (task: Task) => Promise<void>;
  deleteTaskFromDB: (id: string) => Promise<void>;
  loadChatFromDB: () => Promise<void>;
  saveChatToDB: (msg: ChatMessage) => Promise<void>;

  // API sync helpers
  loadFromAPI: () => Promise<void>;
  loadChatFromAPI: () => Promise<void>;
  checkBackendHealth: () => Promise<void>;

  // Task execution (POST /api/tasks/{id}/execute + SSE)
  runTaskExecution: (task: Task) => Promise<void>;
}

export const useStore = create<AppState>((set, get) => ({
  view: 'kanban',
  setView: (v) => set({ view: v }),

  workspaceDir: '',
  setWorkspaceDir: (dir) => set({ workspaceDir: dir }),

  isBackendAvailable: false,
  setBackendAvailable: (v) => set({ isBackendAvailable: v }),

  tasks: [],
  setTasks: (tasks) => set({ tasks }),
  addTask: (task) => set((s) => ({ tasks: [...s.tasks, task] })),
  updateTask: (task) =>
    set((s) => ({
      tasks: s.tasks.map((t) => (t.id === task.id ? task : t)),
      detailTask: s.detailTask?.id === task.id ? task : s.detailTask,
    })),
  removeTask: (id) => set((s) => ({ tasks: s.tasks.filter((t) => t.id !== id) })),

  showCreateModal: false,
  openCreateModal: () =>
    set({
      showCreateModal: true,
      newTaskTitle: '',
      newTaskDescription: '',
      selectedModel: 'gemini-3.5-flash',
      llmPlan: '',
      isGeneratingPlan: false,
      planConversation: '',
    }),
  closeCreateModal: () => set({ showCreateModal: false }),

  selectedTaskId: null,
  detailTask: null,
  openTaskDetail: (task) =>
    set({
      detailTask: task,
      selectedTaskId: task.id,
      streamingContent: task.stream_response || '',
    }),
  closeTaskDetail: () => set({ detailTask: null, selectedTaskId: null, streamingContent: '' }),

  newTaskTitle: '',
  newTaskDescription: '',
  selectedModel: 'gemini-3.5-flash',
  llmPlan: '',
  isGeneratingPlan: false,
  planConversation: '',
  setNewTaskTitle: (v) => set({ newTaskTitle: v }),
  setNewTaskDescription: (v) => set({ newTaskDescription: v }),
  setSelectedModel: (v) => set({ selectedModel: v }),
  setLlmPlan: (v) => set({ llmPlan: v }),
  setIsGeneratingPlan: (v) => set({ isGeneratingPlan: v }),
  setPlanConversation: (v) => set({ planConversation: v }),

  chatMessages: [],
  setChatMessages: (msgs) => set({ chatMessages: msgs }),
  addChatMessage: (msg) => set((s) => ({ chatMessages: [...s.chatMessages, msg] })),

  streamingContent: '',
  setStreamingContent: (v) => set({ streamingContent: v }),
  appendStreamingContent: (v) => set((s) => ({ streamingContent: s.streamingContent + v })),
  stopStreaming: null,
  setStopStreaming: (fn) => set({ stopStreaming: fn }),

  // ── Electron IPC fallback ────────────────────────────────

  async loadFromDB() {
    if (!window.electronAPI) return;
    const tasks = await window.electronAPI.getTasks();
    set({ tasks });
  },

  async saveTaskToDB(task) {
    if (!window.electronAPI) return;
    try {
      await window.electronAPI.updateTask(task);
    } catch {
      await window.electronAPI.createTask(task);
    }
  },

  async deleteTaskFromDB(id) {
    if (!window.electronAPI) return;
    await window.electronAPI.deleteTask(id);
  },

  async loadChatFromDB() {
    if (!window.electronAPI) return;
    const msgs = await window.electronAPI.getChatMessages();
    set({ chatMessages: msgs });
  },

  async saveChatToDB(msg) {
    if (!window.electronAPI) return;
    await window.electronAPI.addChatMessage(msg);
  },

  // ── API syncing ──────────────────────────────────────────

  async loadFromAPI() {
    try {
      const tasks = await api.fetchTasks();
      set({ tasks, isBackendAvailable: true });
    } catch {
      set({ isBackendAvailable: false });
      get().loadFromDB();
    }
  },

  async loadChatFromAPI() {
    try {
      const msgs = await api.fetchChatMessages();
      set({ chatMessages: msgs, isBackendAvailable: true });
    } catch {
      set({ isBackendAvailable: false });
      get().loadChatFromDB();
    }
  },

  async checkBackendHealth() {
    try {
      const res = await fetch('http://127.0.0.1:8765/api/health');
      if (res.ok) {
        set({ isBackendAvailable: true });
        return;
      }
    } catch {
      // backend not running
    }
    set({ isBackendAvailable: false });
  },

  async runTaskExecution(task) {
    const s = get();

    // 1. Make sure the task is in 'in-progress' on local store + backend.
    let current: Task = task;
    if (current.status !== 'in-progress') {
      current = { ...current, status: 'in-progress', updated_at: new Date().toISOString() };
      s.updateTask(current);
      try {
        await api.updateTask(current.id, current);
      } catch (err) {
        console.warn('[runTaskExecution] status PATCH failed:', err);
      }
      await s.saveTaskToDB(current);
    }

    // 2. Clear any prior stream output and kick off SSE.
    set({ streamingContent: '' });

    const cancel = api.executeTaskStream(
      current.id,
      { task_id: current.id, model: current.model, workspace_dir: s.workspaceDir },
      (chunk) => set((st) => ({ streamingContent: st.streamingContent + chunk })),
      async (full) => {
        const next: Task = {
          ...current,
          status: 'in-review',
          stream_response: full,
          updated_at: new Date().toISOString(),
        };
        get().updateTask(next);
        try {
          await api.updateTask(next.id, next);
        } catch (err) {
          console.warn('[runTaskExecution] final PATCH failed:', err);
        }
        await get().saveTaskToDB(next);
        set({ stopStreaming: null });
      },
      (err) => {
        console.error('[runTaskExecution] executeTaskStream failed:', err);
        set((st) => ({
          streamingContent:
            st.streamingContent + `\n\n\u26a0\ufe0f Backend error: ${err.message}\n`,
          stopStreaming: null,
        }));
      },
    );
    set({ stopStreaming: cancel });
  },
}));

// Helper: check if a task can move to a target status
export function canMoveTo(from: TaskStatus, to: TaskStatus, tasks: Task[]): boolean {
  if (from === to) return false;

  // Planning tasks can move to Queue, In Progress, or Archive
  if (from === 'planning') {
    if (to === 'queue') return true;
    if (to === 'in-progress') {
      return !tasks.some((t) => t.status === 'in-progress');
    }
    if (to === 'archive') return true;
    return false;
  }

  // Queue → In Progress only if no task currently in progress
  if (from === 'queue') {
    if (to === 'in-progress') {
      return !tasks.some((t) => t.status === 'in-progress');
    }
    if (to === 'archive') return true;
    return false;
  }

  // In Progress → In Review, Done, Archive
  if (from === 'in-progress') {
    if (to === 'in-review' || to === 'done' || to === 'archive') return true;
    return false;
  }

  // In Review → Done, Archive, In Progress
  if (from === 'in-review') {
    if (to === 'done' || to === 'archive' || to === 'in-progress') {
      if (to === 'in-progress') {
        return !tasks.some((t) => t.status === 'in-progress');
      }
      return true;
    }
    return false;
  }

  // Done → Archive
  if (from === 'done') {
    return to === 'archive';
  }

  // Archive → Planning (restore)
  if (from === 'archive') {
    return to === 'planning';
  }

  return false;
}

export function getMovableTargets(from: TaskStatus, tasks: Task[]): TaskStatus[] {
  const all: TaskStatus[] = ['planning', 'queue', 'in-progress', 'in-review', 'done', 'archive'];
  return all.filter((to) => canMoveTo(from, to as TaskStatus, tasks));
}
