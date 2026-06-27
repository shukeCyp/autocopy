import { useStore } from '../stores/useStore';
import { apiPost, apiGet, createWs } from '../api/client';

export default function TopBar() {
  const { running, setRunning, nodes, setCurrentTaskId, setTasks } = useStore();

  const handleRun = async () => {
    const graphNodes = useStore.getState().nodes;
    const graphEdges = useStore.getState().edges;

    const graph = {
      nodes: graphNodes.map((n) => ({
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
      edges: graphEdges.map((e) => ({
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
          apiGet<any[]>('/tasks').then((tasks) => setTasks(tasks));
        }
      });
    } catch (e) {
      console.error('run failed:', e);
      setRunning(false);
    }
  };

  return (
    <div className="h-11 bg-gray-950 border-b border-gray-800 flex items-center px-4 gap-3 flex-shrink-0">
      <h1 className="text-sm font-bold text-blue-400 mr-2">TK 爆款复刻</h1>
      <button
        onClick={handleRun}
        disabled={running || nodes.length === 0}
        className={`px-4 py-1.5 text-xs rounded-md font-medium transition-colors ${
          running ? 'bg-gray-700 text-gray-500 cursor-not-allowed' : 'bg-green-600 hover:bg-green-500 text-white'
        }`}
      >
        {running ? '⏳ 运行中...' : '▶ 运行'}
      </button>
      <div className="flex-1" />
      <span className="text-[10px] text-gray-600">{nodes.length} 节点</span>
    </div>
  );
}
