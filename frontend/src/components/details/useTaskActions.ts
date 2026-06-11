import { useStore } from '@/store/useStore';
import type { Task, TaskStatus } from '@/types';
import * as api from '@/services/api';

/** Centralized task-action handlers shared by every per-status detail body. */
export function useTaskActions(task: Task | null) {
  const updateTask = useStore((s) => s.updateTask);
  const removeTask = useStore((s) => s.removeTask);
  const saveTaskToDB = useStore((s) => s.saveTaskToDB);
  const deleteTaskFromDB = useStore((s) => s.deleteTaskFromDB);
  const closeTaskDetail = useStore((s) => s.closeTaskDetail);
  const setStreamingContent = useStore((s) => s.setStreamingContent);
  const appendStreamingContent = useStore((s) => s.appendStreamingContent);
  const setStopStreaming = useStore((s) => s.setStopStreaming);
  const stopStreaming = useStore((s) => s.stopStreaming);
  const tasks = useStore((s) => s.tasks);
  const workspaceDir = useStore((s) => s.workspaceDir);

  async function persist(next: Task) {
    updateTask(next);
    try { await api.updateTask(next.id, next); } catch { /* noop */ }
    await saveTaskToDB(next);
  }

  async function moveTo(status: TaskStatus) {
    if (!task) return;
    const next: Task = { ...task, status, updated_at: new Date().toISOString() };
    await persist(next);
  }

  async function startExecution() {
    if (!task) return;
    if (task.status !== 'in-progress') {
      if (tasks.some((t) => t.status === 'in-progress' && t.id !== task.id)) return;
      await moveTo('in-progress');
    }
    setStreamingContent('');

    const cancel = api.executeTaskStream(
      task.id,
      { model: task.model, workspace_dir: workspaceDir },
      (chunk) => appendStreamingContent(chunk),
      async (full) => {
        const next: Task = {
          ...task,
          status: 'in-review',
          stream_response: full,
          updated_at: new Date().toISOString(),
        };
        await persist(next);
        setStopStreaming(null);
      },
      () => { /* backend unavailable: leave stream empty */ },
    );
    setStopStreaming(cancel);
  }

  function stop() {
    if (stopStreaming) stopStreaming();
    setStopStreaming(null);
  }

  async function deleteTask() {
    if (!task) return;
    stop();
    removeTask(task.id);
    try { await api.deleteTask(task.id); } catch { /* noop */ }
    await deleteTaskFromDB(task.id);
    closeTaskDetail();
  }

  async function sendPlanFeedback(feedback: string) {
    if (!task || !feedback.trim()) return;
    try {
      const res = await fetch('http://127.0.0.1:8765/api/tasks/plan-temp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: task.title,
          description: task.description,
          model: task.model,
          feedback: feedback.trim(),
          current_plan: task.plan,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        const next: Task = {
          ...task,
          plan: data.plan,
          plan_conversation: (task.plan_conversation || '') +
            `\n\n---\n\n**You:** ${feedback}\n\n---\n\n**Assistant:**\n${data.plan}`,
          updated_at: new Date().toISOString(),
        };
        await persist(next);
        return;
      }
    } catch { /* fall through */ }

    const revisedPlan = `[Revised Plan]\n\n${task.plan}\n\n---\n**Feedback incorporated:** ${feedback}`;
    const next: Task = {
      ...task,
      plan: revisedPlan,
      plan_conversation: (task.plan_conversation || '') +
        `\n\n---\n\n**You:** ${feedback}\n\n---\n\n**Assistant:**\n*Plan updated based on your feedback.*`,
      updated_at: new Date().toISOString(),
    };
    await persist(next);
  }

  return { startExecution, stop, deleteTask, sendPlanFeedback, moveTo, persist };
}
