import { useStore } from '@/store/useStore';
import { COLUMNS, type TaskStatus } from '@/types';
import KanbanColumn from './KanbanColumn';

export default function KanbanBoard() {
  const tasks = useStore((s) => s.tasks);
  const openCreateModal = useStore((s) => s.openCreateModal);

  const tasksByStatus = (status: TaskStatus) =>
    tasks.filter((t) => t.status === status).sort((a, b) => a.position - b.position);

  const queueCount = tasksByStatus('queue').length;
  const hasInProgress = tasksByStatus('in-progress').length > 0;

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-slate-800/50 bg-slate-900/30">
        <div>
          <h1 className="text-lg font-semibold text-white tracking-tight">Kanban Board</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            {tasks.length} task{tasks.length !== 1 ? 's' : ''} across {COLUMNS.length} columns
          </p>
        </div>
        <div className="flex items-center gap-3">
          {queueCount > 0 && (
            <div className="text-xs text-slate-400 bg-slate-800 px-3 py-1.5 rounded-lg">
              <span className="font-semibold text-blue-400">{queueCount}</span> in Queue
            </div>
          )}
          <button onClick={openCreateModal} className="btn-primary text-sm">
            + New Task
          </button>
        </div>
      </header>

      {/* Columns */}
      <div className="flex-1 overflow-x-auto overflow-y-hidden p-5">
        <div className="flex gap-4 h-full min-h-0">
          {COLUMNS.map((col) => (
            <KanbanColumn
              key={col.status}
              status={col.status}
              title={col.title}
              color={col.color}
              icon={col.icon}
              tasks={tasksByStatus(col.status)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
