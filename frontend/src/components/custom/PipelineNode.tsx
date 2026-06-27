import { memo, useState } from 'react';
import { Handle, Position } from 'reactflow';
import { nodeLabel, paramLabel, portLabel, t, type Language } from '../../i18n';
import { useStore } from '../../stores/useStore';
import { apiUpload } from '../../api/client';

const STATUS_COLORS: Record<string, string> = {
  idle: 'border-[#3c3d42]',
  queued: 'border-[#d79a2b]',
  running: 'border-[#d79a2b] shadow-[0_0_0_1px_rgba(215,154,43,0.45)]',
  done: 'border-[#4c9f70]',
  failed: 'border-[#cc5555]',
  skipped: 'border-[#5b5c62]',
};

const ICONS: Record<string, string> = {
  VideoInput: '📁', TTSExtract: '🎤', SRTRewrite: '✏️',
  VideoMatch: '🎬', TTSGenerate: '🔊', VideoCompose: '🎞️', JianyingExport: '✂️',
};

const PORT_COLORS: Record<string, string> = {
  video_info: '#4da3ff',
  file_path: '#ffcc33',
  srt_content: '#ff7ac8',
  audio_segments: '#b66dff',
  json_data: '#56e36f',
  latent: '#f07bff',
  image: '#35b7ff',
  audio: '#ff6b6b',
  model: '#c48cff',
  clip: '#ffdd33',
  vae: '#ff7070',
};

const PORT_NAME_COLORS: Record<string, string> = {
  viral_video_info: '#4da3ff',
  source_video_info: '#2f7dff',
  video_info: '#4da3ff',
  script_txt: '#ffcc33',
  full_srt: '#ff8c33',
  final_srt: '#ff7ac8',
  srt_path: '#ff7ac8',
  rewritten_srt: '#ffd43b',
  matched_video: '#35b7ff',
  segments_json: '#56e36f',
  review_html: '#b66dff',
  timeline_audio: '#ff6b6b',
  entries_json: '#78d26f',
  tts_entries_json: '#78d26f',
  final_video: '#35b7ff',
  draft_path: '#ffcc33',
};

const PARAM_OPTIONS: Record<string, string[]> = {
  target_language: ['Chinese', 'English'],
  audio_format: ['mp3', 'wav', 'm4a'],
  video_codec: ['libx264', 'h264_videotoolbox', 'copy'],
  audio_codec: ['aac', 'copy'],
  gemini_model: ['gemini-3.5-flash'],
};

function portColor(portType?: string, portName?: string) {
  return (portName && PORT_NAME_COLORS[portName]) || PORT_COLORS[portType || ''] || '#d7b36b';
}

function PipelineNode({ data, selected }: any) {
  const { id, label, nodeType, status, inputs, outputs, params, paramValues, error, language = 'zh', preview = false } = data as any & { language: Language; preview?: boolean };
  const updateNodeParam = useStore((state) => state.updateNodeParam);
  const updateNodeStatus = useStore((state) => state.updateNodeStatus);
  const borderColor = STATUS_COLORS[status] || STATUS_COLORS.idle;
  const icon = ICONS[nodeType] || '⚙️';
  const [editingParam, setEditingParam] = useState<string | null>(null);
  const [draftValue, setDraftValue] = useState('');

  const inputPorts = Object.keys(inputs || {});
  const outputPorts = Object.keys(outputs || {});
  const paramEntries = Object.entries(params || {});
  const isVideoInput = nodeType === 'VideoInput' && params?.path;
  const currentPath = paramValues?.path ?? params?.path?.default ?? '';

  const paramValue = (name: string, spec: any) =>
    paramValues?.[name] !== undefined ? paramValues[name] : spec.default ?? '';

  const updateParamFromInput = (name: string, spec: any, value: string | boolean) => {
    if (spec.param_type === 'bool') {
      updateNodeParam(id, name, value === true || value === 'true');
      return;
    }
    if (spec.param_type === 'int') {
      updateNodeParam(id, name, value === '' ? '' : Number.parseInt(String(value), 10));
      return;
    }
    if (spec.param_type === 'float') {
      updateNodeParam(id, name, value === '' ? '' : Number.parseFloat(String(value)));
      return;
    }
    updateNodeParam(id, name, value);
  };

  const paramOptions = (name: string, spec: any) => {
    if (spec.param_type === 'bool') return ['true', 'false'];
    if (name === 'model' && nodeType === 'TTSGenerate') return ['speech-02-hd', 'speech-02-turbo'];
    if (name === 'model' && nodeType === 'SRTRewrite') return ['gemini-3.5-flash'];
    return spec.options || PARAM_OPTIONS[name] || null;
  };

  const displayParamValue = (name: string, spec: any) => {
    const value = paramValue(name, spec);
    if (spec.param_type === 'bool') {
      if (language === 'zh') return value ? '开启' : '关闭';
      return value ? 'true' : 'false';
    }
    return String(value ?? '');
  };

  const openParamEditor = (name: string, spec: any) => {
    setEditingParam(name);
    setDraftValue(String(paramValue(name, spec) ?? ''));
  };

  const commitParamEditor = (name: string, spec: any) => {
    updateParamFromInput(name, spec, draftValue);
    setEditingParam(null);
  };

  const extractDroppedPath = (event: React.DragEvent<HTMLDivElement>) => {
    const uriList = event.dataTransfer.getData('text/uri-list');
    const text = event.dataTransfer.getData('text/plain');
    const file = event.dataTransfer.files?.[0] as (File & { path?: string }) | undefined;
    const rawPath = file?.path || uriList.split('\n').find((line) => line && !line.startsWith('#')) || text;
    if (!rawPath) return '';
    if (rawPath.startsWith('file://')) {
      try {
        return decodeURIComponent(new URL(rawPath).pathname);
      } catch {
        return rawPath.replace(/^file:\/\//, '');
      }
    }
    return rawPath;
  };

  const applyUploadedPath = async (file: File) => {
    updateNodeStatus(id, 'running', undefined);
    try {
      const uploaded = await apiUpload<{ path: string }>('/files/upload', file);
      updateNodeParam(id, 'path', uploaded.path);
      updateNodeStatus(id, 'idle', undefined);
    } catch (error) {
      console.error('upload failed:', error);
      updateNodeStatus(id, 'failed', t(language, 'node.pathUnavailable'));
    }
  };

  const handleDrop = async (event: React.DragEvent<HTMLDivElement>) => {
    if (!isVideoInput) return;
    event.preventDefault();
    event.stopPropagation();
    const path = extractDroppedPath(event);
    if (path && path !== currentPath) {
      updateNodeParam(id, 'path', path);
      updateNodeStatus(id, 'idle', undefined);
      return;
    }

    const file = event.dataTransfer.files?.[0];
    if (file) {
      await applyUploadedPath(file);
      return;
    }

    updateNodeStatus(id, 'failed', t(language, 'node.pathUnavailable'));
  };

  return (
    <div
      onDragOver={(event) => {
        if (preview || !isVideoInput) return;
        event.preventDefault();
        event.dataTransfer.dropEffect = 'copy';
      }}
      onDrop={preview ? undefined : handleDrop}
      className={`comfy-node min-w-[300px] rounded-xl border ${borderColor} ${selected ? 'selected' : ''} ${preview ? 'preview' : ''}`}
    >
      <div className="comfy-node-title flex h-12 items-center gap-2 px-3">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-lg">{icon}</span>
          <span className="comfy-node-name truncate text-[15px] font-semibold">{nodeLabel(language, nodeType, label, id)}</span>
        </div>
        <span className={`ml-auto h-3 w-3 rounded-full ${
          status === 'done' ? 'bg-[#4c9f70]' :
          status === 'running' ? 'bg-[#d79a2b] animate-pulse' :
          status === 'failed' ? 'bg-[#cc5555]' : 'bg-[#696a70]'
        }`} />
      </div>
      <div className="px-3 py-3">
        <div className="comfy-node-type mb-3 text-[13px] font-medium uppercase">{nodeType}</div>
        {isVideoInput && (
          <div className={`comfy-video-drop mb-2 rounded border border-dashed px-2 py-1.5 text-[10px] ${currentPath ? 'has-path' : ''}`}>
            {currentPath ? `${t(language, 'node.pathCaptured')}: ${String(currentPath).split('/').pop()}` : t(language, 'node.dropVideo')}
            <label className="nodrag mt-1 block cursor-pointer underline">
              {language === 'zh' ? '选择文件' : 'Choose file'}
              <input
                type="file"
                accept="video/*"
                className="hidden"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) applyUploadedPath(file);
                  event.target.value = '';
                }}
              />
            </label>
          </div>
        )}
        <div className="grid grid-cols-2 gap-5">
          <div>
            {inputPorts.length === 0 ? (
              <div className="comfy-port-row text-[10px] text-[#5f6066]">{t(language, 'node.noInputs')}</div>
            ) : inputPorts.map((name) => (
              <div key={name} className="comfy-port-row comfy-port-row-input text-[13px] font-semibold">
                {!preview && (
                  <Handle
                    type="target"
                    position={Position.Left}
                    id={name}
                    className="comfy-port-handle"
                    style={{
                      background: portColor(inputs?.[name]?.port_type, name),
                    }}
                  />
                )}
                <span className="truncate" style={{ color: portColor(inputs?.[name]?.port_type, name) }}>{portLabel(language, name)}</span>
              </div>
            ))}
          </div>
          <div className="text-right">
            {outputPorts.length === 0 ? (
              <div className="comfy-port-row justify-end text-[10px] text-[#5f6066]">{t(language, 'node.noOutputs')}</div>
            ) : outputPorts.map((name) => (
              <div key={name} className="comfy-port-row comfy-port-row-output justify-end text-[13px] font-semibold">
                <span className="truncate" style={{ color: portColor(outputs?.[name]?.port_type, name) }}>{portLabel(language, name)}</span>
                {!preview && (
                  <Handle
                    type="source"
                    position={Position.Right}
                    id={name}
                    className="comfy-port-handle"
                    style={{
                      background: portColor(outputs?.[name]?.port_type, name),
                    }}
                  />
                )}
              </div>
            ))}
          </div>
        </div>
        {paramEntries.length > 0 && (
          <div className="comfy-param-section mt-4 space-y-1.5 border-t pt-3">
            {paramEntries.map(([name, spec]: [string, any]) => {
              const options = paramOptions(name, spec);
              return (
                <div key={name} className="comfy-param-wrap">
                  <div className="comfy-param nodrag nowheel grid grid-cols-[minmax(0,1fr)_minmax(84px,auto)] items-center gap-2 text-[13px] text-[#d9d9d9]">
                    <span className="comfy-param-label min-w-0 truncate">{paramLabel(language, name)}</span>
                    {options ? (
                      <select
                        value={spec.param_type === 'bool' ? String(Boolean(paramValue(name, spec))) : paramValue(name, spec)}
                        onChange={(event) => updateParamFromInput(name, spec, event.target.value)}
                        className="comfy-param-select min-w-0 text-right outline-none"
                      >
                        {options.map((option: string) => (
                          <option key={String(option)} value={String(option)}>
                            {spec.param_type === 'bool' && language === 'zh'
                              ? option === 'true' ? '开启' : '关闭'
                              : String(option)}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <button
                        type="button"
                        onClick={() => openParamEditor(name, spec)}
                        className="comfy-param-value min-w-0 truncate text-right"
                      >
                        {displayParamValue(name, spec) || 'undefined'}
                      </button>
                    )}
                  </div>
                  {editingParam === name && !options && (
                    <div className="comfy-param-popover nodrag nowheel">
                      <input
                        autoFocus
                        type={spec.param_type === 'int' || spec.param_type === 'float' ? 'number' : 'text'}
                        value={draftValue}
                        onChange={(event) => setDraftValue(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter') commitParamEditor(name, spec);
                          if (event.key === 'Escape') setEditingParam(null);
                        }}
                      />
                      <button type="button" onClick={() => commitParamEditor(name, spec)}>
                        {language === 'zh' ? '确定' : 'OK'}
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
        {status !== 'idle' && (
          <div className="comfy-node-status mt-2 rounded px-2 py-1 text-[10px]">{error || status}</div>
        )}
      </div>
    </div>
  );
}

export default memo(PipelineNode);
