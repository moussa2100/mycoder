import { FileText } from 'lucide-react';

/** Reusable rendering of plan text + conversation history. */
export function PlanBlock({ plan, conversation }: { plan: string; conversation?: string }) {
  return (
    <div className="space-y-4">
      <div className="stream-text">
        {plan ? (
          plan.split('\n').map((line, i) => (
            <div key={i} className={lineClass(line)}>{line || '\u00A0'}</div>
          ))
        ) : (
          <div className="flex flex-col items-center justify-center py-12 text-slate-600">
            <FileText size={32} className="mb-3 opacity-50" />
            <p className="text-sm">No plan yet</p>
          </div>
        )}
      </div>

      {conversation && (
        <div className="pt-4 border-t border-slate-800/50">
          <h4 className="text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wide">
            Conversation
          </h4>
          <div className="stream-text text-xs space-y-1">
            {conversation.split('\n').map((line, i) => (
              <div key={i} className={convClass(line)}>{line || '\u00A0'}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function lineClass(line: string): string {
  if (line.startsWith('##')) return 'text-indigo-300 font-semibold mt-3 mb-1';
  if (line.startsWith('###')) return 'text-slate-200 font-medium mt-2';
  if (/^(-|\d+\.)/.test(line)) return 'text-slate-400 ml-2';
  return 'text-slate-500';
}

function convClass(line: string): string {
  if (line.startsWith('**You:**')) return 'text-cyan-400 mt-2';
  if (line.startsWith('**Assistant:**')) return 'text-indigo-400 mt-2';
  if (line.startsWith('---')) return 'text-slate-700';
  return 'text-slate-500';
}
