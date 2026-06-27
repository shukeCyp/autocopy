import { useState } from 'react';
import { useStore } from '../stores/useStore';

export default function NodeDetail() {
  const { nodes, selectedNodeId, setSelectedNodeId, updateNodeParam } = useStore();
  const node = nodes.find((n) => n.id === selectedNodeId);

  if (!node) {
    return (
      <div className="w-64 bg-gray-950 border-l border-gray-800 flex-shrink-0 flex items-center justify-center">
        <div className="text-[10px] text-gray-600 text-center px-4">点击画布上的节点<br/>查看详情</div>
      </div>
    );
  }

  const [tab, setTab] = useState<'params' | 'inputs' | 'outputs' | 'logs'>('params');
  const pvs = node.paramValues || {};

  return (
    <div className="w-64 bg-gray-950 border-l border-gray-800 flex flex-col flex-shrink-0 overflow-y-auto">
      {/* Header */}
      <div className="p-3 border-b border-gray-800">
        <div className="flex items-center justify-between">
          <div className="text-xs font-bold text-white">{node.label}</div>
          <button onClick={() => setSelectedNodeId(null)} className="text-gray-600 hover:text-gray-400">✕</button>
        </div>
        <div className="text-[10px] text-gray-500">{node.type}</div>
        <div className={`text-[10px] mt-1 ${
          node.status === 'done' ? 'text-green-400' :
          node.status === 'running' ? 'text-blue-400' :
          node.status === 'failed' ? 'text-red-400' : 'text-gray-500'
        }`}>
          {node.status}
          {node.error && <span className="text-red-400 ml-1">— {node.error.slice(0, 60)}</span>}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-800">
        {(['params', 'inputs', 'outputs', 'logs'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 py-1.5 text-[10px] ${
              tab === t ? 'text-blue-400 border-b border-blue-400' : 'text-gray-600'
            }`}
          >
            {{ params: '参数', inputs: '输入', outputs: '输出', logs: '日志' }[t]}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="p-3 flex-1">
        {tab === 'params' && Object.entries(node.params).map(([name, spec]) => (
          <div key={name} className="mb-3">
            <div className="text-[10px] text-gray-500 mb-1">{name}</div>
            {spec.param_type === 'bool' ? (
              <label className="flex items-center gap-2 text-xs">
                <input
                  type="checkbox"
                  checked={pvs[name] !== undefined ? pvs[name] : spec.default}
                  onChange={(e) => updateNodeParam(node.id, name, e.target.checked)}
                  className="rounded"
                />
                {spec.description || name}
              </label>
            ) : (
              <input
                type={spec.param_type === 'int' || spec.param_type === 'float' ? 'number' : 'text'}
                value={pvs[name] !== undefined ? pvs[name] : spec.default || ''}
                onChange={(e) => {
                  const val = spec.param_type === 'float' || spec.param_type === 'int'
                    ? Number(e.target.value)
                    : e.target.value;
                  updateNodeParam(node.id, name, val);
                }}
                className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-white"
              />
            )}
            {spec.description && <div className="text-[10px] text-gray-600 mt-0.5">{spec.description}</div>}
          </div>
        ))}
        {tab === 'inputs' && Object.entries(node.inputs).map(([name, spec]) => (
          <div key={name} className="mb-2 text-xs">
            <span className="text-gray-400">{name}</span>
            <span className="text-gray-600 ml-1">({spec.port_type})</span>
            {!spec.required && <span className="text-gray-700 ml-1">可选</span>}
          </div>
        ))}
        {tab === 'outputs' && (
          <>
            {Object.entries(node.outputs).map(([name, spec]) => (
              <div key={name} className="mb-2 text-xs">
                <span className="text-gray-400">{name}</span>
                <span className="text-gray-600 ml-1">({spec.port_type})</span>
                {node.outputs_cache && node.outputs_cache[name] && (
                  <div className="text-[10px] text-green-500 mt-0.5 truncate">{String(node.outputs_cache[name])}</div>
                )}
              </div>
            ))}
            {Object.keys(node.outputs).length === 0 && (
              <div className="text-[10px] text-gray-600">无输出端口</div>
            )}
          </>
        )}
        {tab === 'logs' && (
          <div className="text-[10px] text-gray-600">
            {node.status === 'failed' && node.error ? (
              <div className="text-red-400 whitespace-pre-wrap">{node.error}</div>
            ) : (
              <div>暂无日志</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
