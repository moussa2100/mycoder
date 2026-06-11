import { LayoutGrid, MessageSquare, Sparkles } from 'lucide-react';
import { useStore } from '@/store/useStore';
import type { ViewType } from '@/types';

const navItems: { id: ViewType; label: string; icon: typeof LayoutGrid }[] = [
  { id: 'kanban', label: 'Kanban', icon: LayoutGrid },
  { id: 'chat', label: 'Chat', icon: MessageSquare },
];

export default function Sidebar() {
  const view = useStore((s) => s.view);
  const setView = useStore((s) => s.setView);

  return (
    <aside className="w-56 flex-shrink-0 bg-slate-900 border-r border-slate-800/50 flex flex-col">
      {/* Logo */}
      <div className="h-14 flex items-center gap-2.5 px-5 border-b border-slate-800/50">
        <div className="w-8 h-8 rounded-lg bg-indigo-500/20 flex items-center justify-center">
          <Sparkles className="w-4.5 h-4.5 text-indigo-400" size={18} />
        </div>
        <span className="font-semibold text-base tracking-tight text-white">
          pgimcode
        </span>
      </div>

      {/* Nav Items */}
      <nav className="flex-1 px-3 pt-4 space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = view === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setView(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 ${
                isActive
                  ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 shadow-sm shadow-indigo-500/5'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 border border-transparent'
              }`}
            >
              <Icon size={18} />
              {item.label}
            </button>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-4 py-4 border-t border-slate-800/50">
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          v1.0.0
        </div>
      </div>
    </aside>
  );
}
