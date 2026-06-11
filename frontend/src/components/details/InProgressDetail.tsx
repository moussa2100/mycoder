import { useState } from 'react';
import { Square, ChevronDown, ChevronRight, Loader2, Clock } from 'lucide-react';
import type { Task } from '@/types';
import { useStore } from '@/store/useStore';
import { PlanBlock } from './PlanBlock';
import { StreamBlock } from './StreamBlock';
import { useTaskActions } from './useTaskActions';
import { useElapsedSeconds, formatElapsed } from './useElapsedTime';

/** In-Progress column: live stream + Stop, with plan accessible in a collapsed section. */
export default function InProgressDetail({ task }: { task: Task }) {
  const { stop } = useTaskActions(task);
  const streamingContent = useStore((s) => s.streamingContent);
  const stopStreaming = useStore((s) => s.stopStreaming);
  const [showPlan, setShowPlan] = useState(false);

  const running = !!stopStreaming;
  const elapsed = useElapsedSeconds(task.updated_at, running);

  return (
    <div className="space-y-4">
      {/* Prominent progress banner */}
      <div
        className={`flex items-center gap-3 px-4 py-3 rounded-xl border ${
          running
            ? 'bg-amber-500/5 border-amber-500/30'
            : 'bg-slate-800/40 border-slate-700/40'
        }`}
      >
        {running ? (
          <Loader2 size={18} className="text-amber-400 animate-spin flex-shrink-0" />
        ) : (
          <Clock size={18} className="text-slate-500 flex-shrink-0" />
        )}
        <div className="flex-1 min-w-0">
          <div className={`text-sm font-medium ${running ? 'text-amber-300' : 'text-slate-300'}`}>
            {running ? 'In progress…' : 'Idle'}
          </div>
          <div className="text-xs text-slate-500 mt-0.5">
            {running
              ? 'Agent is working on this task. Output streams below.'
              : 'No active execution. Press Start from another column to run again.'}
          </div>
        </div>
        <div className="flex items-center gap-1.5 text-amber-300 font-mono text-sm tabular-nums">
          <Clock size={13} className="opacity-70" />
          {formatElapsed(elapsed)}
        </div>
        {running && (
          <button onClick={stop} className="btn-danger flex items-center gap-1.5 text-xs ml-2">
            <Square size={12} /> Stop
          </button>
        )}
      </div>

      <StreamBlock content={streamingContent || task.stream_response} running={running} />

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
    </div>
  );
}
