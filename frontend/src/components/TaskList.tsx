import { useEffect } from 'react';
import { useStore } from '../stores/useStore';
import { apiGet, apiDelete } from '../api/client';
import type { Task } from '../types';

export default function TaskList() {
  const { tasks, currentTaskId, setTasks, setCurrentTaskId, setGraph } = useStore();

  const refresh = async () => {
    try {
      const data = await apiGet<Task[]>('/api/tasks');
      setTasks(data);
    } catch {}
  };

  useEffect(() => { refresh(); }, []);

  const selectTask = async (task: Task) => {
    setCurrentTaskId(task.id);
    try {
      const t = await apiGet<Task & { graph_json: string }>(`/tasks/${task.id}`);
      const g = JSON.parse(typeof t.graph_json === 'string' ? t.graph_json : JSON.stringify(t.graph_json));
      setGraph(g.nodes || [], (g.edges || []).map((e: any) => ({
        source_node_id: e.source_node_id, source_port: e.source_port,
        target_node_id: e.target_node_id, target_port: e.target_port,
      })));
    } catch {}
  };

  const deleteTask = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    await apiDelete(`/tasks/${id}`);
    if (currentTaskId === id) setCurrentTaskId(null);
    refresh();
  };

  const STATUS: Record<string, string> = {
    pending: 'text-yellow-400', running: 'text-blue-400',
    done: 'text-green-400', failed: 'text-red-400',
  };

  return (
    <div className="w-56 bg-gray-950 border-r border-gray-800 flex flex-col flex-shrink-0">
      <div className="p-3 text-[10px] text-gray-500 uppercase tracking-wider font-semibold">任务列表</div>
      <div className="flex-1 overflow-y-auto">
        {tasks.map((t) => (
          <div
            key={t.id}
            onClick={() => selectTask(t)}
            className={`px-3 py-2 cursor-pointer border-l-2 text-xs ${
              currentTaskId === t.id
                ? 'border-blue-500 bg-blue-900/20 text-white'
                : 'border-transparent hover:bg-gray-900 text-gray-300'
            }`}
          >
            <div className="truncate font-medium">{t.name || t.id}</div>
            <div className="flex justify-between mt-0.5">
              <span className={`${STATUS[t.status] || 'text-gray-500'} text-[10px]`}>{t.status}</span>
              <span className="text-[10px] text-gray-600">{t.current_step}</span>
            </div>
            <button onClick={(e) => deleteTask(t.id, e)} className="text-[10px] text-gray-600 hover:text-red-400 mt-0.5">删除</button>
          </div>
        ))}
        {tasks.length === 0 && (
          <div className="px-3 py-4 text-[10px] text-gray-600 text-center">暂无任务</div>
        )}
      </div>
    </div>
  );
}
