import { memo } from 'react';
import { Handle, Position } from 'reactflow';

const STATUS_COLORS: Record<string, string> = {
  idle: 'border-gray-600 bg-gray-900',
  queued: 'border-yellow-500 bg-yellow-900/20',
  running: 'border-blue-500 bg-blue-900/30',
  done: 'border-green-500 bg-green-900/20',
  failed: 'border-red-500 bg-red-900/30',
  skipped: 'border-gray-500 bg-gray-800/50',
};

const ICONS: Record<string, string> = {
  VideoInput: '📁', TTSExtract: '🎤', SRTRewrite: '✏️',
  VideoMatch: '🎬', TTSGenerate: '🔊', VideoCompose: '🎞️', JianyingExport: '✂️',
};

function PipelineNode({ data, selected }: any) {
  const { label, nodeType, status, outputs_cache, inputs, outputs } = data;
  const borderColor = STATUS_COLORS[status] || STATUS_COLORS.idle;
  const icon = ICONS[nodeType] || '⚙️';

  const inputPorts = Object.keys(inputs || {});
  const outputPorts = Object.keys(outputs || {});

  return (
    <div className={`rounded-lg border-2 min-w-[140px] ${borderColor} ${selected ? 'ring-2 ring-blue-400' : ''}`}>
      {/* Input handles */}
      {inputPorts.map((name, i) => (
        <Handle
          key={name}
          type="target"
          position={Position.Left}
          id={name}
          style={{ top: 16 + i * 18, background: '#555' }}
        />
      ))}
      <div className="px-3 py-2">
        <div className="flex items-center gap-2 text-xs font-medium text-gray-200">
          <span>{icon}</span>
          <span>{label}</span>
        </div>
        <div className="text-[10px] text-gray-500 mt-0.5">{nodeType}</div>
        {status === 'done' && outputs_cache && Object.keys(outputs_cache).length > 0 && (
          <div className="mt-1 text-[10px] text-green-400">✓ 完成</div>
        )}
        {status === 'running' && (
          <div className="mt-1 text-[10px] text-blue-400 animate-pulse">⟳ 运行中</div>
        )}
        {status === 'failed' && (
          <div className="mt-1 text-[10px] text-red-400">✗ 失败</div>
        )}
      </div>
      {/* Output handles */}
      {outputPorts.map((name, i) => (
        <Handle
          key={name}
          type="source"
          position={Position.Right}
          id={name}
          style={{ top: 16 + i * 18, background: '#555' }}
        />
      ))}
    </div>
  );
}

export default memo(PipelineNode);
