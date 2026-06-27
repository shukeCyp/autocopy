import { useStore } from '../stores/useStore';
import { apiGet } from '../api/client';
import type { Template, NodeData, EdgeData } from '../types';

export default function TemplateDialog() {
  const { templateDialogOpen, setTemplateDialogOpen, templates, setGraph, setCurrentTaskId } = useStore();

  if (!templateDialogOpen) return null;

  const selectTemplate = async (t: Template) => {
    try {
      const data = await apiGet<Template & { graph_json: string }>(`/templates/${t.id}`);
      const g = JSON.parse(data.graph_json || '{}');
      const nodes: NodeData[] = (g.nodes || []).map((n: any) => ({
        ...n,
        status: 'idle',
        paramValues: {},
      }));
      const edges: EdgeData[] = (g.edges || []).map((e: any) => ({
        source_node_id: e.source_node_id, source_port: e.source_port,
        target_node_id: e.target_node_id, target_port: e.target_port,
      }));
      setGraph(nodes, edges);
      setCurrentTaskId(null);
    } catch (e) {
      console.error('load template failed:', e);
    }
    setTemplateDialogOpen(false);
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setTemplateDialogOpen(false)}>
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 w-[480px]" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-sm font-bold text-white mb-4">选择模板</h2>
        <div className="grid grid-cols-2 gap-3 mb-4">
          {templates.map((t) => (
            <div
              key={t.id}
              onClick={() => selectTemplate(t)}
              className="p-4 bg-gray-800 hover:bg-gray-700 rounded-lg cursor-pointer border border-gray-700 hover:border-blue-500 transition-colors"
            >
              <div className="text-xs font-medium text-white">{t.name}</div>
              <div className="text-[10px] text-gray-500 mt-1">{t.builtin ? '内置模板' : '自定义'}</div>
            </div>
          ))}
        </div>
        <button
          onClick={() => setTemplateDialogOpen(false)}
          className="w-full py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs rounded-md"
        >
          取消
        </button>
      </div>
    </div>
  );
}
