import { Lightbulb, ListOrdered, Play, Eye, CheckCircle2, Archive, ArrowRight } from 'lucide-react';
import { useStore } from '@/store/useStore';
import type { Task, TaskStatus } from '@/types';
import KanbanCard from './KanbanCard';

const iconMap: Record<string, typeof Lightbulb> = {
  Lightbulb,
  ListOrdered,
  Play,
  Eye,
  CheckCircle2,
  Archive,
};

interface Props {
  status: TaskStatus;
  title: string;
  color: string;
  icon: string;
  tasks: Task[];
}

export default function KanbanColumn({ status, title, color, icon, tasks }: Props) {
  const IconComp = iconMap[icon] || Lightbulb;

  const isPlanning = status === 'planning';
  const isQueue = status === 'queue';
  const openCreateModal = useStore((s) => s.openCreateModal);
  const allTasks = useStore((s) => s.tasks);
  const updateTask = useStore((s) => s.updateTask);
  const saveTaskToDB = useStore((s) => s.saveTaskToDB);

  const hasInProgress = allTasks.some((t) => t.status === 'in-progress');
  const canStartQueue = isQueue && tasks.length > 0 && !hasInProgress;

  const handleStartQueue = async () => {
    if (!canStartQueue || tasks.length === 0) return;
    const firstInQueue = tasks[0];
    const updated: Task = {
      ...firstInQueue,
      status: 'in-progress',
      updated_at: new Date().toISOString(),
    };
    updateTask(updated);
    await saveTaskToDB(updated);
  };

  return (
    <div className="kanban-column">
      {/* Column Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800/30">
        <div className="flex items-center gap-2">
          <div
            className="w-2.5 h-2.5 rounded-full"
            style={{ backgroundColor: color }}
          />
          <IconComp size={15} className="text-slate-400" />
          <h3 className="text-sm font-semibold text-slate-200">{title}</h3>
          <span className="text-xs text-slate-500 bg-slate-800/50 px-1.5 py-0.5 rounded-md min-w-[20px] text-center">
            {tasks.length}
          </span>
        </div>
        {isPlanning && (
          <button
            onClick={openCreateModal}
            className="w-6 h-6 rounded-lg bg-slate-700/50 hover:bg-slate-600/50 text-slate-400 hover:text-white flex items-center justify-center transition-all text-lg leading-none"
          >
            +
          </button>
        )}
      </div>

      {/* Start Queue Button */}
      {canStartQueue && (
        <div className="px-3 py-2 border-b border-slate-800/20">
          <button
            onClick={handleStartQueue}
            className="w-full py-2 rounded-lg bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/20 hover:border-blue-500/40 text-blue-400 text-xs font-semibold flex items-center justify-center gap-1.5 transition-all"
          >
            <Play size={12} />
            Start Queue
            <ArrowRight size={12} />
          </button>
        </div>
      )}

      {/* Cards */}
      <div className="flex-1 overflow-y-auto p-2 space-y-2 min-h-[100px]">
        {tasks.map((task) => (
          <KanbanCard key={task.id} task={task} />
        ))}
        {tasks.length === 0 && (
          <div className="flex flex-col items-center justify-center py-8 text-slate-600">
            <div className="text-xs">No tasks</div>
          </div>
        )}
      </div>
    </div>
  );
}
