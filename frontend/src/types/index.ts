export interface Task {
  id: string;
  title: string;
  description: string;
  status: TaskStatus;
  model: string;
  plan: string;
  stream_response: string;
  created_at: string;
  updated_at: string;
  position: number;
}

export type TaskStatus =
  | 'planning'
  | 'queue'
  | 'in-progress'
  | 'in-review'
  | 'done'
  | 'archive';

export const COLUMNS: { status: TaskStatus; title: string; color: string; icon: string }[] = [
  { status: 'planning', title: 'Planning', color: '#f59e0b', icon: 'Lightbulb' },
  { status: 'queue', title: 'Queue', color: '#3b82f6', icon: 'ListOrdered' },
  { status: 'in-progress', title: 'In Progress', color: '#8b5cf6', icon: 'Play' },
  { status: 'in-review', title: 'In Review', color: '#06b6d4', icon: 'Eye' },
  { status: 'done', title: 'Done', color: '#10b981', icon: 'CheckCircle2' },
  { status: 'archive', title: 'Archive', color: '#6b7280', icon: 'Archive' },
];

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  model: string;
  created_at: string;
}

export type ViewType = 'kanban' | 'chat';

export interface ElectronAPI {
  getTasks: () => Promise<Task[]>;
  createTask: (task: Task) => Promise<Task>;
  updateTask: (task: Task) => Promise<Task>;
  deleteTask: (id: string) => Promise<{ success: boolean }>;
  getTasksByStatus: (status: TaskStatus) => Promise<Task[]>;
  getChatMessages: () => Promise<ChatMessage[]>;
  addChatMessage: (msg: ChatMessage) => Promise<ChatMessage>;
  clearChat: () => Promise<{ success: boolean }>;
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}
