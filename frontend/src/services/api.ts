/** API service for the pgimcode backend.
 *
 * All API calls go through this module. When running in Electron with a local
 * backend, calls go to http://127.0.0.1:8765. In browser dev mode, Vite
 * proxies /api requests to the backend.
 */

import type { Task, TaskStatus, ChatMessage } from '@/types';

const API_BASE = 'http://127.0.0.1:8765';

// ── Helpers ────────────────────────────────────────────────

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

// ── Tasks ──────────────────────────────────────────────────

export async function fetchTasks(status?: TaskStatus): Promise<Task[]> {
  const qs = status ? `?status=${status}` : '';
  return request<Task[]>(`/api/tasks${qs}`);
}

export async function fetchTask(taskId: string): Promise<Task> {
  return request<Task>(`/api/tasks/${taskId}`);
}

export async function createTask(data: {
  title: string;
  description?: string;
  model?: string;
}): Promise<Task> {
  return request<Task>('/api/tasks', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateTask(
  taskId: string,
  data: Partial<Task>,
): Promise<Task> {
  return request<Task>(`/api/tasks/${taskId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function deleteTask(taskId: string): Promise<void> {
  await request(`/api/tasks/${taskId}`, { method: 'DELETE' });
}

// ── Plan Generation ────────────────────────────────────────

export async function generatePlan(
  taskId: string,
  data: {
    title: string;
    description?: string;
    model?: string;
    feedback?: string;
    current_plan?: string;
  },
): Promise<{ plan: string; conversation: string }> {
  return request(`/api/tasks/${taskId}/plan`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function generatePlanStream(
  taskId: string,
  data: {
    title: string;
    description?: string;
    model?: string;
    feedback?: string;
    current_plan?: string;
  },
  onChunk: (chunk: string) => void,
  onDone: (fullPlan: string) => void,
  onError: (err: Error) => void,
): () => void {
  const controller = new AbortController();
  const url = `${API_BASE}/api/tasks/${taskId}/plan/stream`;

  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const reader = res.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data:')) {
            try {
              const parsed = JSON.parse(line.slice(5).trim());
              if (parsed.event === 'chunk') {
                onChunk(parsed.data);
              } else if (parsed.event === 'done') {
                onDone(parsed.data);
              }
            } catch {
              // SSE parsing issue, skip
            }
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== 'AbortError') onError(err);
    });

  return () => controller.abort();
}

// ── Task Execution ─────────────────────────────────────────

export function executeTaskStream(
  taskId: string,
  data: { model?: string; workspace_dir?: string },
  onChunk: (chunk: string) => void,
  onDone: (fullOutput: string) => void,
  onError: (err: Error) => void,
): () => void {
  const controller = new AbortController();
  const url = `${API_BASE}/api/tasks/${taskId}/execute`;

  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const reader = res.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data:')) {
            try {
              const parsed = JSON.parse(line.slice(5).trim());
              if (parsed.event === 'chunk') {
                onChunk(parsed.data);
              } else if (parsed.event === 'done') {
                onDone(parsed.data);
              }
            } catch {
              // skip
            }
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== 'AbortError') onError(err);
    });

  return () => controller.abort();
}

// ── Chat ───────────────────────────────────────────────────

export async function fetchChatMessages(): Promise<ChatMessage[]> {
  return request<ChatMessage[]>('/api/chat');
}

export async function sendChatMessage(data: {
  message: string;
  model?: string;
  workspace_dir?: string;
}): Promise<ChatMessage> {
  return request<ChatMessage>('/api/chat', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function sendChatMessageStream(
  data: { message: string; model?: string; workspace_dir?: string },
  onChunk: (chunk: string) => void,
  onDone: (fullResponse: string) => void,
  onError: (err: Error) => void,
): () => void {
  const controller = new AbortController();
  const url = `${API_BASE}/api/chat/stream`;

  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const reader = res.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data:')) {
            try {
              const parsed = JSON.parse(line.slice(5).trim());
              if (parsed.event === 'chunk') {
                onChunk(parsed.data);
              } else if (parsed.event === 'done') {
                onDone(parsed.data);
              }
            } catch {
              // skip
            }
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== 'AbortError') onError(err);
    });

  return () => controller.abort();
}

export async function clearChat(): Promise<void> {
  await request('/api/chat', { method: 'DELETE' });
}

// ── Workspace ──────────────────────────────────────────────

export async function validateWorkspace(path: string): Promise<{
  path: string;
  exists: boolean;
  is_directory: boolean;
}> {
  return request('/api/workspace/validate', {
    method: 'POST',
    body: JSON.stringify({ path }),
  });
}
