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

async function readSseStream(
  res: Response,
  onChunk: (chunk: string) => void,
  onDone: (full: string) => void,
): Promise<void> {
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
  const reader = res.body?.getReader();
  if (!reader) throw new Error('No response body');

  const decoder = new TextDecoder();
  let buffer = '';

  const dispatch = (frame: string) => {
    if (!frame.trim()) return;
    let event = 'message';
    const dataLines: string[] = [];

    for (const rawLine of frame.split(/\r?\n/)) {
      if (!rawLine || rawLine.startsWith(':')) continue;
      const colon = rawLine.indexOf(':');
      const field = colon === -1 ? rawLine : rawLine.slice(0, colon);
      let value = colon === -1 ? '' : rawLine.slice(colon + 1);
      if (value.startsWith(' ')) value = value.slice(1);
      if (field === 'event') event = value;
      if (field === 'data') dataLines.push(value);
    }

    let data = dataLines.join('\n');
    if (event === 'message') {
      try {
        const parsed = JSON.parse(data);
        event = parsed.event ?? event;
        data = parsed.data ?? data;
      } catch {
        event = 'chunk';
      }
    }

    if (event === 'chunk') onChunk(data);
    if (event === 'done') onDone(data);
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let match = buffer.match(/\r?\n\r?\n/);
    while (match?.index !== undefined) {
      dispatch(buffer.slice(0, match.index));
      buffer = buffer.slice(match.index + match[0].length);
      match = buffer.match(/\r?\n\r?\n/);
    }
  }

  buffer += decoder.decode();
  dispatch(buffer);
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
      await readSseStream(res, onChunk, onDone);
    })
    .catch((err) => {
      if (err.name !== 'AbortError') onError(err);
    });

  return () => controller.abort();
}

// ── Task Execution ─────────────────────────────────────────

export function executeTaskStream(
  taskId: string,
  data: { task_id?: string; model?: string; workspace_dir?: string },
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
      await readSseStream(res, onChunk, onDone);
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
      await readSseStream(res, onChunk, onDone);
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
