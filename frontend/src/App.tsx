import { useEffect } from 'react';
import { useStore } from '@/store/useStore';
import Sidebar from '@/components/Sidebar';
import KanbanBoard from '@/components/KanbanBoard';
import ChatPanel from '@/components/ChatPanel';
import CreateTaskModal from '@/components/CreateTaskModal';
import TaskDetailModal from '@/components/TaskDetailModal';

export default function App() {
  const view = useStore((s) => s.view);
  const loadFromDB = useStore((s) => s.loadFromDB);
  const loadChatFromDB = useStore((s) => s.loadChatFromDB);

  useEffect(() => {
    loadFromDB();
    loadChatFromDB();
  }, []);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-950">
      <Sidebar />
      <main className="flex-1 flex flex-col overflow-hidden">
        {view === 'kanban' ? <KanbanBoard /> : <ChatPanel />}
      </main>
      <CreateTaskModal />
      <TaskDetailModal />
    </div>
  );
}
