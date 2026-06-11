import { useState } from 'react';
import { Loader2, Send, Play } from 'lucide-react';
import type { Task } from '@/types';
import { PlanBlock } from './PlanBlock';
import { useTaskActions } from './useTaskActions';

/** Planning column: plan + conversation history + feedback input + Start. */
export default function PlanningDetail({ task }: { task: Task }) {
  const { startExecution, sendPlanFeedback } = useTaskActions(task);
  const [feedback, setFeedback] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!feedback.trim() || busy) return;
    setBusy(true);
    try {
      await sendPlanFeedback(feedback);
      setFeedback('');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <PlanBlock plan={task.plan} conversation={task.plan_conversation} />

      <div className="pt-4 border-t border-slate-800/50 space-y-2">
        <label className="text-xs font-medium text-slate-400 block">
          Send feedback to modify the plan
        </label>
        <div className="flex gap-2">
          <input
            type="text"
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && submit()}
            placeholder="e.g., Add error handling, break down step 2…"
            className="input-field flex-1 text-sm"
            disabled={busy}
          />
          <button
            onClick={submit}
            disabled={!feedback.trim() || busy}
            className="btn-primary flex items-center gap-1.5 text-sm px-4"
          >
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />} Send
          </button>
        </div>
      </div>

      <div className="pt-2">
        <button onClick={startExecution} className="btn-primary flex items-center gap-1.5 text-sm">
          <Play size={13} /> Move to In Progress &amp; Start
        </button>
      </div>
    </div>
  );
}
