import { memo, useEffect, useState } from 'react';
import type { CSSProperties, ReactNode } from 'react';
import {
  AudioOutlined,
  BranchesOutlined,
  EditOutlined,
  ExportOutlined,
  FolderOpenOutlined,
  ScissorOutlined,
  SoundOutlined,
  VideoCameraOutlined,
} from '@ant-design/icons';
import { Handle, Position } from 'reactflow';
import { nodeLabel, paramLabel, portLabel, t, type Language } from '../../i18n';
import { useStore } from '../../stores/useStore';
import { apiGet, apiPost, apiUpload } from '../../api/client';

const STATUS_COLORS: Record<string, string> = {
  idle: 'border-[#3c3d42]',
  queued: 'border-[var(--accent)]',
  running: 'border-[var(--accent)] shadow-[0_0_0_1px_var(--accent)]',
  done: 'border-[#4c9f70]',
  failed: 'border-[#cc5555]',
  skipped: 'border-[#5b5c62]',
};

const NODE_TITLE_ICONS: Record<string, { icon: ReactNode; color: string; bg: string }> = {
  VideoInput: { icon: <FolderOpenOutlined />, color: '#45a3ff', bg: 'rgba(69, 163, 255, 0.16)' },
  VideoAudioExtract: { icon: <AudioOutlined />, color: '#38bdf8', bg: 'rgba(56, 189, 248, 0.16)' },
  VocalSeparation: { icon: <SoundOutlined />, color: '#f97316', bg: 'rgba(249, 115, 22, 0.16)' },
  VoiceVAD: { icon: <AudioOutlined />, color: '#a855f7', bg: 'rgba(168, 85, 247, 0.16)' },
  DominantSpeaker: { icon: <BranchesOutlined />, color: '#eab308', bg: 'rgba(234, 179, 8, 0.16)' },
  SegmentASR: { icon: <EditOutlined />, color: '#ec4899', bg: 'rgba(236, 72, 153, 0.16)' },
  TTSExtract: { icon: <AudioOutlined />, color: '#22c55e', bg: 'rgba(34, 197, 94, 0.16)' },
  SRTRewrite: { icon: <EditOutlined />, color: '#a855f7', bg: 'rgba(168, 85, 247, 0.16)' },
  VideoMatch: { icon: <BranchesOutlined />, color: '#38bdf8', bg: 'rgba(56, 189, 248, 0.16)' },
  VideoMatchVMF: { icon: <BranchesOutlined />, color: '#0ea5e9', bg: 'rgba(14, 165, 233, 0.16)' },
  TTSGenerate: { icon: <SoundOutlined />, color: '#f43f5e', bg: 'rgba(244, 63, 94, 0.16)' },
  VideoCompose: { icon: <ScissorOutlined />, color: '#14b8a6', bg: 'rgba(20, 184, 166, 0.16)' },
  JianyingMerge: { icon: <ExportOutlined />, color: '#7c8cff', bg: 'rgba(124, 140, 255, 0.16)' },
  JianyingExport: { icon: <ExportOutlined />, color: '#6475ff', bg: 'rgba(100, 117, 255, 0.16)' },
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
  srt_content: '#ff7ac8',
  srt_path: '#ff7ac8',
  rewritten_srt: '#ffd43b',
  matched_video: '#35b7ff',
  segments_json: '#56e36f',
  review_html: '#b66dff',
  vmf_results_json: '#b66dff',
  timeline_audio: '#ff6b6b',
  vocals_audio: '#ff6b6b',
  accompaniment_audio: '#35b7ff',
  separated_dir: '#ffcc33',
  audio_path: '#ffcc33',
  speech_segments_json: '#b66dff',
  speech_segments_dir: '#ffcc33',
  dominant_segments_json: '#f97316',
  speaker_report_json: '#78d26f',
  dominant_speaker_id: '#56e36f',
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
  const {
    id,
    label,
    nodeType,
    status,
    inputs,
    outputs,
    params,
    paramValues,
    language = 'zh',
    preview = false,
    executing = false,
    validationIssues = [],
  } = data as any & { language: Language; preview?: boolean };
  const updateNodeParam = useStore((state) => state.updateNodeParam);
  const updateNodeStatus = useStore((state) => state.updateNodeStatus);
  const borderColor = STATUS_COLORS[status] || STATUS_COLORS.idle;
  const titleIcon = NODE_TITLE_ICONS[nodeType] || { icon: <VideoCameraOutlined />, color: '#8b8c90', bg: 'rgba(139, 140, 144, 0.16)' };
  const [editingParam, setEditingParam] = useState<string | null>(null);
  const [openSelectParam, setOpenSelectParam] = useState<string | null>(null);
  const [draftValue, setDraftValue] = useState('');
  const [modelFiles, setModelFiles] = useState<string[]>([]);

  const inputPorts = Object.keys(inputs || {});
  const outputPorts = Object.keys(outputs || {});
  const paramEntries = Object.entries(params || {});
  const issueCount = validationIssues.length;
  const hasModelFileParam = Boolean(params?.whisper_model || params?.vad_model);
  const isVideoInput = nodeType === 'VideoInput' && params?.path;
  const currentPath = paramValues?.path ?? params?.path?.default ?? '';

  useEffect(() => {
    if (!hasModelFileParam) return;
    apiGet<string[]>('/files/models')
      .then(setModelFiles)
      .catch(() => setModelFiles([]));
  }, [hasModelFileParam]);

  useEffect(() => {
    if (!editingParam && !openSelectParam) return;

    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target as HTMLElement;
      if (target.closest('.comfy-param-popover, .comfy-param-menu, .comfy-param-value, .comfy-param-arrow')) return;
      setEditingParam(null);
      setOpenSelectParam(null);
    };

    document.addEventListener('pointerdown', handlePointerDown, true);
    return () => document.removeEventListener('pointerdown', handlePointerDown, true);
  }, [editingParam, openSelectParam]);

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

  const chooseDirectoryParam = async (name: string) => {
    try {
      const result = await apiPost<{ path: string }>('/files/select-directory');
      if (result.path) {
        updateNodeParam(id, name, result.path);
      }
      setEditingParam(null);
      setOpenSelectParam(null);
    } catch (error) {
      console.error('directory selection failed:', error);
      updateNodeStatus(id, 'failed', language === 'zh' ? '选择目录失败' : 'Directory selection failed');
    }
  };

  const paramOptions = (name: string, spec: any) => {
    if (spec.param_type === 'bool') return ['true', 'false'];
    if (name === 'whisper_model' || name === 'vad_model') return modelFiles;
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
    setOpenSelectParam(null);
    setEditingParam(name);
    setDraftValue(String(paramValue(name, spec) ?? ''));
  };

  const commitParamEditor = (name: string, spec: any) => {
    updateParamFromInput(name, spec, draftValue);
    setEditingParam(null);
  };

  const numericStep = (spec: any) => spec.param_type === 'float' ? 0.1 : 1;

  const nudgeParam = (name: string, spec: any, direction: -1 | 1) => {
    if (spec.param_type !== 'int' && spec.param_type !== 'float') return;
    const current = Number(paramValue(name, spec) || 0);
    const next = current + numericStep(spec) * direction;
    updateNodeParam(id, name, spec.param_type === 'int' ? Math.round(next) : Number(next.toFixed(3)));
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
      className={`comfy-node status-${status} min-w-[300px] rounded-xl border ${borderColor} ${selected ? 'selected' : ''} ${executing ? 'executing' : ''} ${issueCount > 0 ? 'has-issues' : ''} ${preview ? 'preview' : ''}`}
    >
      <div className="comfy-node-title flex h-12 items-center gap-2 px-3">
        <div className="flex items-center gap-2 min-w-0">
          <span className="comfy-node-title-icon" style={{ color: titleIcon.color, background: titleIcon.bg }}>{titleIcon.icon}</span>
          <span className="comfy-node-name truncate text-[15px] font-semibold">{nodeLabel(language, nodeType, label, id)}</span>
        </div>
        {issueCount > 0 && (
          <span className="comfy-node-issue-badge">{issueCount}</span>
        )}
        {(status === 'running' || executing) && (
          <span className="comfy-node-running-badge">{t(language, 'status.running')}</span>
        )}
        <span className={`${status === 'running' || executing ? '' : 'ml-auto'} h-3 w-3 rounded-full ${
          status === 'done' ? 'bg-[#4c9f70]' :
          status === 'running' || executing ? 'bg-[var(--accent)] animate-pulse' :
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
                      '--handle-color': portColor(inputs?.[name]?.port_type, name),
                    } as CSSProperties}
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
                      '--handle-color': portColor(outputs?.[name]?.port_type, name),
                    } as CSSProperties}
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
                    <button
                      type="button"
                      className="comfy-param-arrow left"
                      disabled={spec.param_type !== 'int' && spec.param_type !== 'float'}
                      onClick={(event) => {
                        event.stopPropagation();
                        nudgeParam(name, spec, -1);
                      }}
                      aria-label={language === 'zh' ? '减少' : 'Decrease'}
                    />
                    <span className="comfy-param-label min-w-0 truncate">{paramLabel(language, name)}</span>
                    {name === 'draft_folder' ? (
                      <button
                        type="button"
                        onClick={() => chooseDirectoryParam(name)}
                        className="comfy-param-value min-w-0 text-right"
                      >
                        {displayParamValue(name, spec) || (language === 'zh' ? '选择目录' : 'Choose folder')}
                      </button>
                    ) : options ? (
                      <button
                        type="button"
                        className="comfy-param-value comfy-param-select-trigger min-w-0 text-right"
                        onClick={() => {
                          setEditingParam(null);
                          setOpenSelectParam(openSelectParam === name ? null : name);
                        }}
                      >
                        {displayParamValue(name, spec) || 'undefined'}
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={() => openParamEditor(name, spec)}
                        className="comfy-param-value min-w-0 text-right"
                      >
                        {displayParamValue(name, spec) || 'undefined'}
                      </button>
                    )}
                    <button
                      type="button"
                      className="comfy-param-arrow right"
                      disabled={spec.param_type !== 'int' && spec.param_type !== 'float'}
                      onClick={(event) => {
                        event.stopPropagation();
                        nudgeParam(name, spec, 1);
                      }}
                      aria-label={language === 'zh' ? '增加' : 'Increase'}
                    />
                  </div>
                  {openSelectParam === name && options && (
                    <div className="comfy-param-menu nodrag nowheel">
                      {options.length === 0 && (
                        <div className="comfy-param-menu-empty">
                          {language === 'zh' ? 'model 目录暂无模型文件' : 'No model files in model/'}
                        </div>
                      )}
                      {options.map((option: string) => {
                        const label = spec.param_type === 'bool' && language === 'zh'
                          ? option === 'true' ? '开启' : '关闭'
                          : String(option);
                        const selectedOption = String(spec.param_type === 'bool' ? Boolean(paramValue(name, spec)) : paramValue(name, spec)) === String(option);
                        return (
                          <button
                            type="button"
                            key={String(option)}
                            className={selectedOption ? 'active' : ''}
                            onClick={() => {
                              updateParamFromInput(name, spec, option);
                              setOpenSelectParam(null);
                            }}
                          >
                            {label}
                          </button>
                        );
                      })}
                    </div>
                  )}
                  {editingParam === name && !options && (
                    <div className="comfy-param-popover nodrag nowheel">
                      <div className="comfy-param-popover-title">{paramLabel(language, name)}</div>
                      {spec.param_type === 'int' || spec.param_type === 'float' ? (
                        <input
                          autoFocus
                          type="number"
                          value={draftValue}
                          onChange={(event) => setDraftValue(event.target.value)}
                          onKeyDown={(event) => {
                            if (event.key === 'Enter') commitParamEditor(name, spec);
                            if (event.key === 'Escape') setEditingParam(null);
                          }}
                        />
                      ) : (
                        <textarea
                          autoFocus
                          value={draftValue}
                          onChange={(event) => setDraftValue(event.target.value)}
                          onKeyDown={(event) => {
                            if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') commitParamEditor(name, spec);
                            if (event.key === 'Escape') setEditingParam(null);
                          }}
                        />
                      )}
                      <div className="comfy-param-popover-actions">
                        <button type="button" className="secondary" onClick={() => setEditingParam(null)}>
                          {language === 'zh' ? '取消' : 'Cancel'}
                        </button>
                        <button type="button" onClick={() => commitParamEditor(name, spec)}>
                          {language === 'zh' ? '确定' : 'OK'}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default memo(PipelineNode);
