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
  const stopStreaming = useStore((s) => s.stopStreaming);
  const setStopStreaming = useStore((s) => s.setStopStreaming);
  const tasks = useStore((s) => s.tasks);
  const runTaskExecution = useStore((s) => s.runTaskExecution);

  async function persist(next: Task) {
    updateTask(next);
    try {
      await api.updateTask(next.id, next);
    } catch (err) {
      console.warn('[useTaskActions] api.updateTask failed:', err);
    }
    await saveTaskToDB(next);
  }

  async function moveTo(status: TaskStatus) {
    if (!task) return;
    const next: Task = { ...task, status, updated_at: new Date().toISOString() };
    await persist(next);
  }

  async function startExecution() {
    if (!task) return;
    if (tasks.some((t) => t.status === 'in-progress' && t.id !== task.id)) return;
    await runTaskExecution(task);
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
    // Use the per-task plan endpoint so the backend persists the revised plan
    // to the SQLite DB. Falls back to a local-only update if backend is offline.
    try {
      const data = await api.generatePlan(task.id, {
        title: task.title,
        description: task.description,
        model: task.model,
        feedback: feedback.trim(),
        current_plan: task.plan,
      });
      const next: Task = {
        ...task,
        plan: data.plan,
        plan_conversation: data.conversation ||
          (task.plan_conversation || '') +
            `\n\n---\n\n**You:** ${feedback}\n\n---\n\n**Assistant:**\n${data.plan}`,
        updated_at: new Date().toISOString(),
      };
      updateTask(next);
      await saveTaskToDB(next);
      return;
    } catch (err) {
      console.warn('[useTaskActions] api.generatePlan failed, falling back local:', err);
    }

    const revisedPlan = `[Revised Plan]\n\n${task.plan}\n\n---\n**Feedback incorporated:** ${feedback}`;
    const next: Task = {
      ...task,
      plan: revisedPlan,
      plan_conversation: (task.plan_conversation || '') +
        `\n\n---\n\n**You:** ${feedback}\n\n---\n\n**Assistant:**\n*Plan updated based on your feedback (offline mode).*`,
      updated_at: new Date().toISOString(),
    };
    await persist(next);
  }

  return { startExecution, stop, deleteTask, sendPlanFeedback, moveTo, persist };
}
