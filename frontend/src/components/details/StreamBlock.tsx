import { Loader2, Terminal } from 'lucide-react';

/** Reusable rendering of stream/execution output. */
export function StreamBlock({
  content,
  running,
  empty,
}: {
  content: string;
  running?: boolean;
  empty?: React.ReactNode;
}) {
  return (
    <div className="bg-slate-950/60 border border-slate-800/50 rounded-xl p-4 min-h-[200px]">
      <div className="flex items-center gap-2 mb-3 pb-3 border-b border-slate-800/50">
        <Terminal size={14} className="text-slate-500" />
        <span className="text-xs text-slate-500 font-mono">task-execution</span>
        {running && (
          <span className="text-[10px] text-amber-400 font-medium ml-auto flex items-center gap-1">
            <Loader2 size={10} className="animate-spin" /> Running
          </span>
        )}
        {!running && content && (
          <span className="text-[10px] text-emerald-400 font-medium ml-auto">Complete</span>
        )}
      </div>
      <div className="stream-text">
        {content ? (
          content.split('\n').map((line, i) => (
            <div key={i} className={streamClass(line)}>{line || '\u00A0'}</div>
          ))
        ) : (
          empty ?? (
            <div className="flex flex-col items-center justify-center py-12 text-slate-600">
              <Terminal size={32} className="mb-3 opacity-50" />
              <p className="text-sm">No execution output yet</p>
            </div>
          )
        )}
      </div>
    </div>
  );
}

function streamClass(line: string): string {
  if (line.includes('✅') || line.includes('successfully') || line.includes('complete')) {
    return 'text-emerald-400';
  }
  if (line.includes('│') || line.includes('├') || line.includes('└')) return 'text-slate-500';
  return 'text-slate-400';
}
