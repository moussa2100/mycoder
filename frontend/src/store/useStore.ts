import { create } from 'zustand';
import type { Task, TaskStatus, ChatMessage, ViewType } from '@/types';

function genId(): string {
  return crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2);
}

interface AppState {
  // Navigation
  view: ViewType;
  setView: (v: ViewType) => void;

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

  // Streaming (for In Progress task detail)
  streamingContent: string;
  setStreamingContent: (v: string) => void;
  appendStreamingContent: (v: string) => void;

  // DB sync helpers
  loadFromDB: () => Promise<void>;
  saveTaskToDB: (task: Task) => Promise<void>;
  deleteTaskFromDB: (id: string) => Promise<void>;
  loadChatFromDB: () => Promise<void>;
  saveChatToDB: (msg: ChatMessage) => Promise<void>;
}

export const useStore = create<AppState>((set, get) => ({
  view: 'kanban',
  setView: (v) => set({ view: v }),

  tasks: [],
  setTasks: (tasks) => set({ tasks }),
  addTask: (task) => set((s) => ({ tasks: [...s.tasks, task] })),
  updateTask: (task) =>
    set((s) => ({ tasks: s.tasks.map((t) => (t.id === task.id ? task : t)) })),
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
  openTaskDetail: (task) => set({ detailTask: task, selectedTaskId: task.id, streamingContent: task.stream_response || '' }),
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
