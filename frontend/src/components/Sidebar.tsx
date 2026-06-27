import { useEffect } from 'react';
import { useStore } from '../stores/useStore';
import { apiGet, apiDelete } from '../api/client';
import type { Task, Template, NodeData, EdgeData } from '../types';

export default function Sidebar() {
  const {
    tasks, currentTaskId, setTasks, setCurrentTaskId, setGraph,
    templates, setTemplates,
  } = useStore();

  // Load templates on mount
  useEffect(() => {
    apiGet<Template[]>('/templates').then(setTemplates).catch(() => {});
  }, []);

  // Load tasks on mount
  useEffect(() => {
    apiGet<Task[]>('/tasks').then(setTasks).catch(() => {});
  }, []);

  const loadTemplate = async (t: Template) => {
    try {
      const data = await apiGet<Template & { graph_json: string }>(`/templates/${t.id}`);
      const g = JSON.parse(data.graph_json || '{}');
      const newNodes: NodeData[] = (g.nodes || []).map((n: any) => ({
        ...n,
        status: 'idle' as const,
        paramValues: {},
      }));
      const newEdges: EdgeData[] = (g.edges || []).map((e: any) => ({
        source_node_id: e.source_node_id, source_port: e.source_port,
        target_node_id: e.target_node_id, target_port: e.target_port,
      }));
      setGraph(newNodes, newEdges);
      setCurrentTaskId(null);
    } catch (e) {
      console.error('load template failed:', e);
    }
  };

  const loadTask = async (task: Task) => {
    setCurrentTaskId(task.id);
    try {
      const t = await apiGet<Task & { graph_json: string }>(`/tasks/${task.id}`);
      const g = JSON.parse(typeof t.graph_json === 'string' ? t.graph_json : JSON.stringify(t.graph_json));
      setGraph(
        (g.nodes || []).map((n: any) => ({ ...n, paramValues: n.paramValues || {} })),
        (g.edges || []).map((e: any) => ({
          source_node_id: e.source_node_id, source_port: e.source_port,
          target_node_id: e.target_node_id, target_port: e.target_port,
        }))
      );
    } catch {}
  };

  const deleteTask = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    await apiDelete(`/tasks/${id}`);
    if (currentTaskId === id) {
      setCurrentTaskId(null);
      setGraph([], []);
    }
    apiGet<Task[]>('/tasks').then(setTasks).catch(() => {});
  };

  const handleNewWorkflow = () => {
    // Load the first template (quick Chinese) by default
    if (templates.length > 0) {
      loadTemplate(templates[0]);
    }
  };

  const STATUS_COLORS: Record<string, string> = {
    pending: 'text-yellow-400', running: 'text-blue-400',
    done: 'text-green-400', failed: 'text-red-400',
  };

  const ICONS: Record<string, string> = {
    quick_chinese: '🇨🇳', quick_english: '🇺🇸', tts_only: '🎤',
  };

  return (
    <div className="w-60 bg-gray-950 border-r border-gray-800 flex flex-col flex-shrink-0 overflow-y-auto">
      {/* Workflows section */}
      <div className="p-3 border-b border-gray-800">
        <div className="flex items-center justify-between mb-2">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold">工作流模板</div>
          <button
            onClick={handleNewWorkflow}
            className="text-[10px] text-blue-400 hover:text-blue-300"
          >
            + 加载默认
          </button>
        </div>
        {templates.map((t) => (
          <div
            key={t.id}
            onClick={() => loadTemplate(t)}
            className="p-2.5 mb-1.5 rounded-lg cursor-pointer border transition-colors bg-gray-800/50 border-gray-700 hover:border-blue-500 hover:bg-gray-800"
          >
            <div className="flex items-center gap-2">
              <span className="text-sm">{ICONS[t.id] || '📦'}</span>
              <div className="flex-1 min-w-0">
                <div className="text-xs font-medium text-gray-200 truncate">{t.name}</div>
                <div className="text-[10px] text-gray-500">{t.builtin ? '内置 · ' : ''}{t.id === 'quick_chinese' ? '6步全流程' : t.id === 'quick_english' ? '6步全流程' : '仅TTS'}</div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Task history section */}
      <div className="flex-1 flex flex-col">
        <div className="p-3 text-[10px] text-gray-500 uppercase tracking-wider font-semibold sticky top-0 bg-gray-950">
          任务历史
        </div>
        <div className="flex-1 overflow-y-auto">
          {tasks.map((t) => (
            <div
              key={t.id}
              onClick={() => loadTask(t)}
              className={`px-3 py-2.5 cursor-pointer border-l-2 text-xs ${
                currentTaskId === t.id
                  ? 'border-blue-500 bg-blue-900/20 text-white'
                  : 'border-transparent hover:bg-gray-900 text-gray-300'
              }`}
            >
              <div className="truncate font-medium">{t.name || t.id.slice(0, 16)}</div>
              <div className="flex items-center justify-between mt-0.5">
                <span className={`${STATUS_COLORS[t.status] || 'text-gray-500'} text-[10px]`}>
                  {t.status === 'done' ? '✓ 完成' : t.status === 'running' ? '⟳ 运行中' : t.status === 'failed' ? '✗ 失败' : t.status}
                </span>
                <button
                  onClick={(e) => deleteTask(t.id, e)}
                  className="text-[10px] text-gray-600 hover:text-red-400 opacity-0 group-hover:opacity-100"
                >
                  🗑
                </button>
              </div>
            </div>
          ))}
          {tasks.length === 0 && (
            <div className="px-3 py-4 text-[10px] text-gray-600 text-center">暂无历史任务</div>
          )}
        </div>
      </div>
    </div>
  );
}
