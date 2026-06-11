import { Play } from 'lucide-react';
import type { Task } from '@/types';
import { useStore } from '@/store/useStore';
import { PlanBlock } from './PlanBlock';
import { useTaskActions } from './useTaskActions';

/** Queue column: readonly plan + queue context + Start (blocked if another task is running). */
export default function QueueDetail({ task }: { task: Task }) {
  const { startExecution } = useTaskActions(task);
  const tasks = useStore((s) => s.tasks);
  const queueTasks = tasks
    .filter((t) => t.status === 'queue')
    .sort((a, b) => a.position - b.position);
  const position = queueTasks.findIndex((t) => t.id === task.id);
  const blocked = tasks.some((t) => t.status === 'in-progress');

  return (
    <div className="space-y-4">
      <PlanBlock plan={task.plan} conversation={task.plan_conversation} />

      <div className="pt-4 border-t border-slate-800/50 text-xs text-slate-500 space-y-1">
        <p>
          Queue position:{' '}
          <span className="text-slate-300 font-medium">
            {position >= 0 ? position + 1 : '—'} of {queueTasks.length}
          </span>
        </p>
        {blocked && (
          <p className="text-amber-400">
            Another task is currently In Progress. This task will start when that one completes.
          </p>
        )}
      </div>

      <div className="pt-2">
        <button
          onClick={startExecution}
          disabled={blocked}
          className="btn-primary flex items-center gap-1.5 text-sm disabled:opacity-50"
        >
          <Play size={13} /> Start Now
        </button>
      </div>
    </div>
  );
}
