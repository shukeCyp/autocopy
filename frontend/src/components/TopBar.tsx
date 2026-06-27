import { useStore } from '../stores/useStore';
import { apiPost, apiGet, createWs } from '../api/client';
import type { Template } from '../types';

export default function TopBar() {
  const { setTemplateDialogOpen, running, setRunning, nodes, setCurrentTaskId, setTasks } = useStore();

  const handleNewTask = async () => {
    // Fetch templates first
    try {
      const templates = await apiGet<Template[]>('/api/templates');
      useStore.getState().setTemplates(templates);
    } catch {}
    setTemplateDialogOpen(true);
  };

  const handleRun = async () => {
    const graph = {
      nodes: useStore.getState().nodes.map((n) => ({
        id: n.id, type: n.type, label: n.label,
        x: n.x, y: n.y, status: n.status,
        inputs: Object.fromEntries(Object.entries(n.inputs).map(([k, v]) => [k, { ...v, port_type: (v as any).port_type }])),
        outputs: Object.fromEntries(Object.entries(n.outputs).map(([k, v]) => [k, { ...v, port_type: (v as any).port_type }])),
        params: Object.fromEntries(Object.entries(n.params).map(([k, v]) => {
          const pv = n.paramValues || {};
          const spec = v as any;
          return [k, { ...spec, default: pv[k] !== undefined ? pv[k] : spec.default }];
        })),
      })),
      edges: useStore.getState().edges.map((e) => ({
        source_node_id: e.source_node_id, source_port: e.source_port,
        target_node_id: e.target_node_id, target_port: e.target_port,
      })),
    };

    setRunning(true);
    try {
      const { task_id } = await apiPost<{ task_id: string }>('/graph/run', {
        graph_json: JSON.stringify(graph),
        task_name: 'New Task',
      });
      setCurrentTaskId(task_id);

      // Connect WebSocket
      const ws = createWs(task_id, (event) => {
        if (event.type === 'node_status') {
          useStore.getState().updateNodeStatus(event.node_id, event.data.status);
        } else if (event.type === 'node_done') {
          useStore.getState().updateNodeStatus(event.node_id, 'done', undefined, event.data.outputs);
        } else if (event.type === 'node_error') {
          useStore.getState().updateNodeStatus(event.node_id, 'failed', event.data.error);
        } else if (event.type === 'graph_complete' || event.type === 'graph_error') {
          setRunning(false);
          ws.close();
          // Refresh tasks
          apiGet<any[]>('/api/tasks').then((tasks) => setTasks(tasks));
        }
      });
    } catch (e) {
      console.error('run failed:', e);
      setRunning(false);
    }
  };

  return (
    <div className="h-12 bg-gray-950 border-b border-gray-800 flex items-center px-4 gap-3 flex-shrink-0">
      <h1 className="text-sm font-bold text-blue-400 mr-4">TK 爆款复刻</h1>
      <button onClick={handleNewTask} className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded-md transition-colors">
        + 新建任务
      </button>
      <button
        onClick={handleRun}
        disabled={running || nodes.length === 0}
        className={`px-4 py-1.5 text-xs rounded-md transition-colors font-medium ${
          running ? 'bg-gray-700 text-gray-500 cursor-not-allowed' : 'bg-green-600 hover:bg-green-500 text-white'
        }`}
      >
        {running ? '⏳ 运行中...' : '▶ 运行'}
      </button>
      <div className="flex-1" />
      <span className="text-[10px] text-gray-600">{nodes.length} nodes</span>
    </div>
  );
}
