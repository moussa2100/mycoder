import { useState } from 'react';
import { CheckCircle2, RefreshCw, ChevronDown, ChevronRight } from 'lucide-react';
import type { Task } from '@/types';
import { PlanBlock } from './PlanBlock';
import { StreamBlock } from './StreamBlock';
import { useTaskActions } from './useTaskActions';

/** In-Review column: final stream + plan side-by-side accordion + Approve / Re-run. */
export default function InReviewDetail({ task }: { task: Task }) {
  const { moveTo, startExecution } = useTaskActions(task);
  const [showPlan, setShowPlan] = useState(true);

  return (
    <div className="space-y-4">
      <StreamBlock content={task.stream_response} running={false} />

      <div className="pt-2 border-t border-slate-800/50">
        <button
          onClick={() => setShowPlan((v) => !v)}
          className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200"
        >
          {showPlan ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          {showPlan ? 'Hide plan' : 'Show plan'}
        </button>
        {showPlan && (
          <div className="mt-3">
            <PlanBlock plan={task.plan} conversation={task.plan_conversation} />
          </div>
        )}
      </div>

      <div className="pt-4 border-t border-slate-800/50 flex items-center gap-2">
        <button
          onClick={() => moveTo('done')}
          className="btn-primary flex items-center gap-1.5 text-sm"
        >
          <CheckCircle2 size={13} /> Approve &amp; Mark Done
        </button>
        <button
          onClick={startExecution}
          className="btn-ghost flex items-center gap-1.5 text-sm text-slate-300 hover:text-white"
        >
          <RefreshCw size={13} /> Re-run
        </button>
      </div>
    </div>
  );
}
