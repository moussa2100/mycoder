import { useState } from 'react';
import { Archive, ChevronDown, ChevronRight } from 'lucide-react';
import type { Task } from '@/types';
import { PlanBlock } from './PlanBlock';
import { StreamBlock } from './StreamBlock';
import { useTaskActions } from './useTaskActions';

/** Done column: read-only summary of plan + final output + Archive action. */
export default function DoneDetail({ task }: { task: Task }) {
  const { moveTo } = useTaskActions(task);
  const [showStream, setShowStream] = useState(true);

  return (
    <div className="space-y-4">
      <PlanBlock plan={task.plan} conversation={task.plan_conversation} />

      <div className="pt-2 border-t border-slate-800/50">
        <button
          onClick={() => setShowStream((v) => !v)}
          className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200"
        >
          {showStream ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          {showStream ? 'Hide execution output' : 'Show execution output'}
        </button>
        {showStream && (
          <div className="mt-3">
            <StreamBlock content={task.stream_response} running={false} />
          </div>
        )}
      </div>

      <div className="pt-4 border-t border-slate-800/50">
        <button
          onClick={() => moveTo('archive')}
          className="btn-ghost flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-200"
        >
          <Archive size={13} /> Archive
        </button>
      </div>
    </div>
  );
}
