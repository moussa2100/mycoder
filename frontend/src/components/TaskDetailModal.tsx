import { useState } from 'react';
import { X, Clock, Play, Square, Trash2, Loader2, Terminal, FileText } from 'lucide-react';
import { useStore } from '@/store/useStore';
import type { TaskStatus } from '@/types';
import { COLUMNS } from '@/types';

type DetailTab = 'plan' | 'stream';

export default function TaskDetailModal() {
  const task = useStore((s) => s.detailTask);
  const close = useStore((s) => s.closeTaskDetail);
  const updateTask = useStore((s) => s.updateTask);
  const removeTask = useStore((s) => s.removeTask);
  const saveTaskToDB = useStore((s) => s.saveTaskToDB);
  const deleteTaskFromDB = useStore((s) => s.deleteTaskFromDB);
  const streamingContent = useStore((s) => s.streamingContent);
  const appendStreamingContent = useStore((s) => s.appendStreamingContent);
  const setStreamingContent = useStore((s) => s.setStreamingContent);
  const tasks = useStore((s) => s.tasks);

  const [activeTab, setActiveTab] = useState<DetailTab>('plan');
  const [isRunning, setIsRunning] = useState(task?.status === 'in-progress' && !!task?.stream_response);
  const [showStopConfirm, setShowStopConfirm] = useState(false);

  if (!task) return null;

  const column = COLUMNS.find((c) => c.status === task.status);
  const borderColor = column?.color || '#6b7280';

  const handleStartTask = async () => {
    // Move to in-progress if not already
    if (task.status !== 'in-progress') {
      const hasInProgress = tasks.some((t) => t.status === 'in-progress' && t.id !== task.id);
      if (hasInProgress) return;

      const updated = { ...task, status: 'in-progress' as TaskStatus, updated_at: new Date().toISOString() };
      updateTask(updated);
      await saveTaskToDB(updated);
    }

    setIsRunning(true);
    setActiveTab('stream');

    // Simulate streaming response
    const steps = [
      'Initializing task execution...\n',
      '├─ Loading context and dependencies\n',
      '├─ Analyzing task requirements\n',
      '├─ Setting up execution environment\n',
      '│  └─ Environment ready\n',
      '├─ Executing step 1: Research\n',
      '│  ├─ Searching codebase...\n',
      '│  ├─ Found 12 relevant files\n',
      '│  └─ Research complete\n',
      '├─ Executing step 2: Design\n',
      '│  ├─ Drafting architecture\n',
      '│  ├─ Reviewing design patterns\n',
      '│  └─ Design approved\n',
      '├─ Executing step 3: Implementation\n',
      '│  ├─ Creating new files...\n',
      '│  ├─ Modifying existing code...\n',
      '│  ├─ Adding tests...\n',
      '│  └─ Implementation complete\n',
      '├─ Executing step 4: Testing\n',
      '│  ├─ Running unit tests...\n',
      '│  ├─ Running integration tests...\n',
      '│  ├─ All tests passing ✓\n',
      '│  └─ Testing complete\n',
      '└─ Task completed successfully!\n\n',
      '──────────────────────────\n',
      '✅ Task execution finished.\n',
      '   - 4/4 steps completed\n',
      '   - 0 errors\n',
      '   - Duration: 3.2s\n',
    ];

    setStreamingContent('');
    for (const step of steps) {
      await new Promise((r) => setTimeout(r, 300 + Math.random() * 400));
      appendStreamingContent(step);
    }

    // Save stream to task
    const finalStream = steps.join('');
    const updated = {
      ...task,
      status: 'in-review' as TaskStatus,
      stream_response: finalStream,
      updated_at: new Date().toISOString(),
    };
    updateTask(updated);
    await saveTaskToDB(updated);
    setIsRunning(false);
  };

  const handleStop = async () => {
    setIsRunning(false);
    setShowStopConfirm(false);
    const updated = { ...task, updated_at: new Date().toISOString() };
    updateTask(updated);
    await saveTaskToDB(updated);
  };

  const handleDelete = async () => {
    if (!showStopConfirm && task.status === 'in-progress') {
      setShowStopConfirm(true);
      return;
    }
    removeTask(task.id);
    await deleteTaskFromDB(task.id);
    close();
  };

  return (
    <div className="modal-backdrop" onClick={close}>
      <div className="modal-panel max-w-2xl max-h-[85vh] flex flex-col" onClick={(e) => e.stopPropagation()} style={{ borderTopWidth: '3px', borderTopColor: borderColor }}>
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800/50">
          <div className="flex items-center gap-3 min-w-0">
            <div
              className="w-3 h-3 rounded-full flex-shrink-0"
              style={{ backgroundColor: borderColor }}
            />
            <div className="min-w-0">
              <h2 className="text-lg font-semibold text-white truncate">{task.title}</h2>
              <p className="text-xs text-slate-500 mt-0.5">
                {column?.title} · {task.model} ·{' '}
                {new Date(task.created_at).toLocaleDateString()}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            {task.status === 'in-progress' && isRunning && (
              <button onClick={handleStop} className="btn-danger text-xs flex items-center gap-1.5">
                <Square size={13} /> Stop
              </button>
            )}
            {(task.status === 'planning' || task.status === 'queue') && (
              <button onClick={handleStartTask} className="btn-primary text-xs flex items-center gap-1.5">
                <Play size={13} /> Start
              </button>
            )}
            {showStopConfirm ? (
              <button onClick={handleDelete} className="btn-danger text-xs flex items-center gap-1.5">
                <Trash2 size={13} /> Confirm Delete
              </button>
            ) : (
              <button onClick={handleDelete} className="btn-ghost text-xs flex items-center gap-1.5 text-slate-500 hover:text-rose-400">
                <Trash2 size={13} /> {task.status === 'in-progress' ? 'Stop & Delete' : 'Delete'}
              </button>
            )}
            <button onClick={close} className="p-2 rounded-lg hover:bg-slate-800 text-slate-500 hover:text-slate-300 transition-all ml-1">
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-slate-800/50 px-6">
          <button
            onClick={() => setActiveTab('plan')}
            className={`px-4 py-2.5 text-sm font-medium transition-all border-b-2 -mb-px flex items-center gap-2 ${
              activeTab === 'plan'
                ? 'text-indigo-400 border-indigo-500'
                : 'text-slate-500 border-transparent hover:text-slate-300'
            }`}
          >
            <FileText size={14} />
            Plan
          </button>
          <button
            onClick={() => setActiveTab('stream')}
            className={`px-4 py-2.5 text-sm font-medium transition-all border-b-2 -mb-px flex items-center gap-2 ${
              activeTab === 'stream'
                ? 'text-indigo-400 border-indigo-500'
                : 'text-slate-500 border-transparent hover:text-slate-300'
            }`}
          >
            <Terminal size={14} />
            Stream
            {isRunning && (
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
            )}
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {activeTab === 'plan' && (
            <div className="stream-text">
              {task.plan ? (
                task.plan.split('\n').map((line, i) => (
                  <div key={i} className={line.startsWith('##') ? 'text-indigo-300 font-semibold mt-3 mb-1' : line.startsWith('###') ? 'text-slate-200 font-medium mt-2' : line.startsWith('-') || line.startsWith('1.') || line.startsWith('2.') || line.startsWith('3.') || line.startsWith('4.') || line.startsWith('5.') ? 'text-slate-400 ml-2' : 'text-slate-500'}>
                    {line || '\u00A0'}
                  </div>
                ))
              ) : (
                <div className="flex flex-col items-center justify-center py-12 text-slate-600">
                  <FileText size={32} className="mb-3 opacity-50" />
                  <p className="text-sm">No plan generated yet</p>
                </div>
              )}
            </div>
          )}

          {activeTab === 'stream' && (
            <div className="bg-slate-950/60 border border-slate-800/50 rounded-xl p-4 min-h-[200px]">
              <div className="flex items-center gap-2 mb-3 pb-3 border-b border-slate-800/50">
                <Terminal size={14} className="text-slate-500" />
                <span className="text-xs text-slate-500 font-mono">task-execution</span>
                {isRunning && (
                  <span className="text-[10px] text-amber-400 font-medium ml-auto flex items-center gap-1">
                    <Loader2 size={10} className="animate-spin" />
                    Running
                  </span>
                )}
                {!isRunning && streamingContent && (
                  <span className="text-[10px] text-emerald-400 font-medium ml-auto">Complete</span>
                )}
              </div>
              <div className="stream-text">
                {streamingContent ? (
                  streamingContent.split('\n').map((line, i) => (
                    <div
                      key={i}
                      className={
                        line.includes('✅') || line.includes('successfully') || line.includes('complete')
                          ? 'text-emerald-400'
                          : line.includes('│') || line.includes('├') || line.includes('└')
                          ? 'text-slate-500'
                          : 'text-slate-400'
                      }
                    >
                      {line || '\u00A0'}
                      {isRunning && i === streamingContent.split('\n').length - 1 && (
                        <span className="inline-block w-2 h-4 bg-indigo-400 ml-0.5 animate-stream-cursor" />
                      )}
                    </div>
                  ))
                ) : (
                  <div className="flex flex-col items-center justify-center py-12 text-slate-600">
                    <Terminal size={32} className="mb-3 opacity-50" />
                    <p className="text-sm">No execution output yet</p>
                    {(task.status === 'planning' || task.status === 'queue') && (
                      <button onClick={handleStartTask} className="btn-primary text-xs mt-3 flex items-center gap-1.5">
                        <Play size={12} /> Start Task
                      </button>
                    )}
                  </div>
                )}
                {isRunning && (
                  <span className="inline-block w-2 h-4 bg-indigo-400 ml-0.5 animate-stream-cursor" />
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-800/50 flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <Clock size={12} />
            Updated {new Date(task.updated_at).toLocaleString()}
          </div>
          <span className="text-[10px] text-slate-600 font-mono">ID: {task.id.slice(0, 8)}</span>
        </div>
      </div>
    </div>
  );
}
