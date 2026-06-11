import { X, Trash2 } from 'lucide-react';
import { useStore } from '@/store/useStore';
import { COLUMNS } from '@/types';
import { useTaskActions } from './details/useTaskActions';
import PlanningDetail from './details/PlanningDetail';
import QueueDetail from './details/QueueDetail';
import InProgressDetail from './details/InProgressDetail';
import InReviewDetail from './details/InReviewDetail';
import DoneDetail from './details/DoneDetail';
import ArchiveDetail from './details/ArchiveDetail';

/** Shell modal that picks a per-status body component. */
export default function TaskDetailModal() {
  const task = useStore((s) => s.detailTask);
  const close = useStore((s) => s.closeTaskDetail);
  const { deleteTask } = useTaskActions(task);

  if (!task) return null;

  const column = COLUMNS.find((c) => c.status === task.status);
  const borderColor = column?.color || '#6b7280';

  const Body = (() => {
    switch (task.status) {
      case 'planning': return <PlanningDetail task={task} />;
      case 'queue': return <QueueDetail task={task} />;
      case 'in-progress': return <InProgressDetail task={task} />;
      case 'in-review': return <InReviewDetail task={task} />;
      case 'done': return <DoneDetail task={task} />;
      case 'archive': return <ArchiveDetail task={task} />;
      default: return null;
    }
  })();

  return (
    <div className="modal-backdrop" onClick={close}>
      <div
        className="modal-panel max-w-2xl max-h-[85vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
        style={{ borderTopWidth: '3px', borderTopColor: borderColor }}
      >
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
                {column?.title} · {task.model} · {new Date(task.created_at).toLocaleDateString()}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            <button
              onClick={deleteTask}
              className="btn-ghost text-xs flex items-center gap-1.5 text-slate-500 hover:text-rose-400"
            >
              <Trash2 size={13} /> Delete
            </button>
            <button
              onClick={close}
              className="p-2 rounded-lg hover:bg-slate-800 text-slate-500 hover:text-slate-300 transition-all ml-1"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Body (per-status) */}
        <div className="flex-1 overflow-y-auto p-6">{Body}</div>
      </div>
    </div>
  );
}
