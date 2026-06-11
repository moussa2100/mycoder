import { useState } from 'react';
import { MoreHorizontal, GripVertical, Clock, ChevronRight } from 'lucide-react';
import { useStore, canMoveTo } from '@/store/useStore';
import type { Task, TaskStatus } from '@/types';
import { COLUMNS } from '@/types';

interface Props {
  task: Task;
}

export default function KanbanCard({ task }: Props) {
  const [showMenu, setShowMenu] = useState(false);
  const updateTask = useStore((s) => s.updateTask);
  const removeTask = useStore((s) => s.removeTask);
  const saveTaskToDB = useStore((s) => s.saveTaskToDB);
  const deleteTaskFromDB = useStore((s) => s.deleteTaskFromDB);
  const openTaskDetail = useStore((s) => s.openTaskDetail);
  const runTaskExecution = useStore((s) => s.runTaskExecution);
  const tasks = useStore((s) => s.tasks);

  const isInProgress = task.status === 'in-progress';
  const [showStopConfirm, setShowStopConfirm] = useState(false);

  const handleMove = async (to: TaskStatus) => {
    if (!canMoveTo(task.status, to, tasks)) return;
    setShowMenu(false);

    // Moving to 'in-progress' must actually invoke the agent, not just
    // update the column. Delegate to the store's runTaskExecution action.
    if (to === 'in-progress') {
      openTaskDetail({ ...task, status: 'in-progress' });
      await runTaskExecution(task);
      return;
    }

    const updated: Task = {
      ...task,
      status: to,
      updated_at: new Date().toISOString(),
    };
    updateTask(updated);
    try {
      const { updateTask: apiUpdate } = await import('@/services/api');
      await apiUpdate(task.id, updated);
    } catch { /* fallback */ }
    await saveTaskToDB(updated);
  };

  const handleDelete = async () => {
    if (isInProgress && !showStopConfirm) {
      setShowStopConfirm(true);
      return;
    }
    removeTask(task.id);
    try {
      const { deleteTask: apiDelete } = await import('@/services/api');
      await apiDelete(task.id);
    } catch { /* fallback */ }
    await deleteTaskFromDB(task.id);
    setShowMenu(false);
    setShowStopConfirm(false);
  };

  const column = COLUMNS.find((c) => c.status === task.status);
  const borderColor = column?.color || '#6b7280';

  const dateLabel = new Date(task.created_at).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  });

  return (
    <div
      className="glass-card group cursor-pointer"
      style={{ borderLeftWidth: '3px', borderLeftColor: borderColor }}
      onClick={() => openTaskDetail(task)}
    >
      <div className="p-3">
        {/* Header Row */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-1.5 min-w-0">
            <GripVertical size={12} className="text-slate-600 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
            <h4 className="text-sm font-medium text-slate-200 truncate">{task.title}</h4>
          </div>
          <div className="relative flex-shrink-0" onClick={(e) => e.stopPropagation()}>
            <button
              onClick={() => setShowMenu(!showMenu)}
              className="p-1 rounded-md hover:bg-slate-700/50 text-slate-500 hover:text-slate-300 transition-all opacity-0 group-hover:opacity-100"
            >
              <MoreHorizontal size={14} />
            </button>
            {showMenu && (
              <div className="absolute right-0 top-7 w-40 bg-slate-800 border border-slate-700 rounded-xl shadow-xl z-30 py-1 animate-fade-in">
                <div className="px-3 py-1.5 text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
                  Move to
                </div>
                {(['planning', 'queue', 'in-progress', 'in-review', 'done', 'archive'] as TaskStatus[]).map((s) => {
                  if (!canMoveTo(task.status, s, tasks)) return null;
                  const col = COLUMNS.find((c) => c.status === s);
                  return (
                    <button
                      key={s}
                      onClick={() => handleMove(s)}
                      className="w-full text-left px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-700/50 flex items-center gap-2 transition-colors"
                    >
                      <div className="w-2 h-2 rounded-full" style={{ backgroundColor: col?.color }} />
                      {col?.title}
                    </button>
                  );
                })}
                <div className="border-t border-slate-700/50 mt-1 pt-1">
                  {isInProgress && showStopConfirm ? (
                    <button
                      onClick={handleDelete}
                      className="w-full text-left px-3 py-1.5 text-xs text-rose-400 hover:bg-rose-500/10 transition-colors"
                    >
                      Confirm Delete
                    </button>
                  ) : (
                    <button
                      onClick={handleDelete}
                      className="w-full text-left px-3 py-1.5 text-xs text-rose-400 hover:bg-rose-500/10 transition-colors"
                    >
                      {isInProgress ? 'Stop & Delete' : 'Delete'}
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Model badge */}
        <div className="flex items-center gap-2 mt-2">
          <span className="text-[10px] text-slate-500 bg-slate-800/70 px-1.5 py-0.5 rounded-md font-mono">
            {task.model}
          </span>
          <span className="flex items-center gap-1 text-[10px] text-slate-600">
            <Clock size={10} />
            {dateLabel}
          </span>
        </div>

        {/* Plan snippet */}
        {task.plan && (
          <p className="text-xs text-slate-500 mt-2 line-clamp-2 leading-relaxed">
            {task.plan.slice(0, 80)}{task.plan.length > 80 ? '...' : ''}
          </p>
        )}

        {/* View details */}
        <div className="flex items-center gap-1 mt-2 text-[11px] text-indigo-400/70 group-hover:text-indigo-400 transition-colors">
          <span>View details</span>
          <ChevronRight size={11} />
        </div>
      </div>
    </div>
  );
}
