import { RotateCcw } from 'lucide-react';
import type { Task } from '@/types';
import { PlanBlock } from './PlanBlock';
import { StreamBlock } from './StreamBlock';
import { useTaskActions } from './useTaskActions';

/** Archive column: read-only history + Restore to Planning. */
export default function ArchiveDetail({ task }: { task: Task }) {
  const { moveTo } = useTaskActions(task);

  return (
    <div className="space-y-4">
      <PlanBlock plan={task.plan} conversation={task.plan_conversation} />

      {task.stream_response && (
        <div className="pt-2 border-t border-slate-800/50">
          <h4 className="text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wide">
            Execution output
          </h4>
          <StreamBlock content={task.stream_response} running={false} />
        </div>
      )}

      <div className="pt-4 border-t border-slate-800/50">
        <button
          onClick={() => moveTo('planning')}
          className="btn-ghost flex items-center gap-1.5 text-sm text-slate-300 hover:text-white"
        >
          <RotateCcw size={13} /> Restore to Planning
        </button>
      </div>
    </div>
  );
}
