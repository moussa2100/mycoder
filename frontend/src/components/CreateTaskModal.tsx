import { useState } from 'react';
import { X, Sparkles, Send, Check, Loader2 } from 'lucide-react';
import { useStore } from '@/store/useStore';
import * as api from '@/services/api';
import type { Task } from '@/types';

const MODELS = [
  { value: 'gemini-3.5-flash', label: 'Gemini 3.5 Flash' },
  { value: 'gemini-3.5-pro-preview', label: 'Gemini 3.5 Pro' },
  { value: 'gemini-3.1-pro-preview', label: 'Gemini 3.1 Pro' },
  { value: 'deepseek-v4-flash', label: 'DeepSeek V4 Flash' },
  { value: 'deepseek-v4-pro', label: 'DeepSeek V4 Pro' },
  { value: 'nemotron-3-ultra-550b', label: 'Nemotron 3 Ultra 550B' },
];

export default function CreateTaskModal() {
  const show = useStore((s) => s.showCreateModal);
  const close = useStore((s) => s.closeCreateModal);
  const title = useStore((s) => s.newTaskTitle);
  const description = useStore((s) => s.newTaskDescription);
  const model = useStore((s) => s.selectedModel);
  const plan = useStore((s) => s.llmPlan);
  const isGenerating = useStore((s) => s.isGeneratingPlan);
  const planConversation = useStore((s) => s.planConversation);
  const setTitle = useStore((s) => s.setNewTaskTitle);
  const setDescription = useStore((s) => s.setNewTaskDescription);
  const setModel = useStore((s) => s.setSelectedModel);
  const setPlan = useStore((s) => s.setLlmPlan);
  const setIsGenerating = useStore((s) => s.setIsGeneratingPlan);
  const setPlanConversation = useStore((s) => s.setPlanConversation);
  const addTask = useStore((s) => s.addTask);
  const saveTaskToDB = useStore((s) => s.saveTaskToDB);
  const tasks = useStore((s) => s.tasks);

  const [feedbackInput, setFeedbackInput] = useState('');

  if (!show) return null;

  const handleSendToLLM = async () => {
    if (!title.trim()) return;

    setIsGenerating(true);
    setPlanConversation('');

    try {
      const res = await fetch('http://127.0.0.1:8765/api/tasks/plan-temp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: title.trim(),
          description: description.trim(),
          model,
        }),
      });
      if (!res.ok) {
        const body = await res.text().catch(() => '');
        throw new Error(`Backend ${res.status} ${res.statusText}\n${body}`);
      }
      const data = await res.json();
      setPlanConversation(
        `**You:** Generate a plan for: "${title.trim()}"\n\n---\n\n**Assistant:**\n${data.plan}`
      );
      setPlan(data.plan);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error('[CreateTaskModal] plan-temp failed:', err);
      setPlanConversation(
        `ERROR calling POST http://127.0.0.1:8765/api/tasks/plan-temp\n\n${msg}`
      );
      setPlan('');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSendFeedback = async () => {
    if (!feedbackInput.trim()) return;

    setIsGenerating(true);
    const currentConversation = planConversation;

    try {
      const res = await fetch('http://127.0.0.1:8765/api/tasks/plan-temp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: title.trim(),
          description: description.trim(),
          model,
          feedback: feedbackInput.trim(),
          current_plan: plan,
        }),
      });
      if (!res.ok) {
        const body = await res.text().catch(() => '');
        throw new Error(`Backend ${res.status} ${res.statusText}\n${body}`);
      }
      const data = await res.json();
      setPlanConversation(
        currentConversation +
          `\n\n---\n\n**You:** ${feedbackInput}\n\n---\n\n**Assistant:**\n${data.plan}`
      );
      setPlan(data.plan);
      setFeedbackInput('');
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error('[CreateTaskModal] plan-temp (feedback) failed:', err);
      setPlanConversation(
        currentConversation +
          `\n\n---\n\nERROR calling POST http://127.0.0.1:8765/api/tasks/plan-temp\n\n${msg}`
      );
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSave = async () => {
    if (!title.trim()) return;

    const now = new Date().toISOString();
    const position = tasks.filter((t) => t.status === 'planning').length;

    // Try the real API first: create on backend, then PATCH the plan + conversation.
    try {
      const created = await api.createTask({
        title: title.trim(),
        description: description.trim(),
        model,
      });
      let serverTask: Task = created;
      if (plan || planConversation) {
        try {
          serverTask = await api.updateTask(created.id, {
            plan,
            plan_conversation: planConversation,
          });
        } catch {
          serverTask = { ...created, plan, plan_conversation: planConversation };
        }
      }
      addTask(serverTask);
      close();
      return;
    } catch {
      // Backend unreachable \u2014 fall back to local-only with a client UUID.
    }

    const localTask: Task = {
      id: crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36),
      title: title.trim(),
      description: description.trim(),
      status: 'planning',
      model,
      plan,
      plan_conversation: planConversation,
      stream_response: '',
      created_at: now,
      updated_at: now,
      position,
    };
    addTask(localTask);
    await saveTaskToDB(localTask);
    close();
  };

  return (
    <div className="modal-backdrop" onClick={close}>
      <div className="modal-panel max-w-2xl max-h-[90vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800/50">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-amber-500/10 flex items-center justify-center">
              <Sparkles size={16} className="text-amber-400" />
            </div>
            <h2 className="text-lg font-semibold text-white">New Task</h2>
          </div>
          <button onClick={close} className="p-2 rounded-lg hover:bg-slate-800 text-slate-500 hover:text-slate-300 transition-all">
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {/* Task Title */}
          <div>
            <label className="text-xs font-medium text-slate-400 mb-1.5 block">Task Title *</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Enter task title..."
              className="input-field"
              autoFocus
            />
          </div>

          {/* Description */}
          <div>
            <label className="text-xs font-medium text-slate-400 mb-1.5 block">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe the task in detail..."
              rows={3}
              className="input-field resize-none"
            />
          </div>

          {/* Model Selector */}
          <div>
            <label className="text-xs font-medium text-slate-400 mb-1.5 block">Model</label>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="input-field"
            >
              {MODELS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>

          {/* Generate Plan Button */}
          {!plan && (
            <button
              onClick={handleSendToLLM}
              disabled={!title.trim() || isGenerating}
              className="btn-primary w-full flex items-center justify-center gap-2"
            >
              {isGenerating ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  Analyzing...
                </>
              ) : (
                <>
                  <Sparkles size={16} />
                  Generate Plan with LLM
                </>
              )}
            </button>
          )}

          {/* LLM Plan Display */}
          {planConversation && (
            <div className="bg-slate-800/50 border border-slate-700/30 rounded-xl overflow-hidden">
              <div className="px-4 py-2 border-b border-slate-700/30 bg-slate-800/70 flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-emerald-400" />
                <span className="text-xs font-medium text-slate-400">LLM Response</span>
              </div>
              <div className="p-4 stream-text max-h-64 overflow-y-auto">
                {planConversation.split('\n').map((line, i) => (
                  <div key={i}>{line || '\u00A0'}</div>
                ))}
              </div>
            </div>
          )}

          {/* Feedback input (after plan generated) */}
          {plan && (
            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-400 block">
                Send feedback to modify the plan
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={feedbackInput}
                  onChange={(e) => setFeedbackInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSendFeedback()}
                  placeholder="Suggest modifications..."
                  className="input-field flex-1"
                />
                <button
                  onClick={handleSendFeedback}
                  disabled={!feedbackInput.trim()}
                  className="btn-primary px-3"
                >
                  <Send size={16} />
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-800/50 flex items-center justify-between">
          <p className="text-xs text-slate-500">
            Task will be created in <span className="text-amber-400 font-medium">Planning</span>
          </p>
          <div className="flex gap-2">
            <button onClick={close} className="btn-secondary text-sm">
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={!title.trim()}
              className="btn-primary text-sm flex items-center gap-1.5"
            >
              <Check size={15} />
              Save Task
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
