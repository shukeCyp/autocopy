import { useEffect, useState } from 'react';
import { useStore } from '../stores/useStore';
import { t as tr } from '../i18n';
import { apiPost } from '../api/client';

export default function NodeDetail() {
  const [tab, setTab] = useState<'params' | 'inputs' | 'outputs' | 'logs'>('params');
  const { nodes, selectedNodeId, setSelectedNodeId, updateNodeParam, language } = useStore();
  const node = nodes.find((n) => n.id === selectedNodeId);
  const logs = node?.logs || [];
  const validationIssues = node?.validationIssues || [];

  useEffect(() => {
    if (node?.status === 'failed') {
      setTab('logs');
    }
  }, [node?.id, node?.status]);

  if (!node) {
    return null;
  }

  const pvs = node.paramValues || {};
  const paramOptions = (name: string, spec: any) => {
    if (spec.param_type === 'bool') return ['true', 'false'];
    if (spec.options) return spec.options;
    if (name === 'target_language') return ['Chinese', 'English'];
    if (name === 'audio_format') return ['mp3', 'wav', 'm4a'];
    if (name === 'video_codec') return ['libx264', 'h264_videotoolbox', 'copy'];
    if (name === 'audio_codec') return ['aac', 'copy'];
    if (name === 'model' && node.type === 'TTSGenerate') return ['speech-02-hd', 'speech-02-turbo'];
    if (name === 'model' && node.type === 'SRTRewrite') return ['gemini-3.5-flash'];
    return null;
  };

  const chooseDirectoryParam = async (name: string) => {
    const result = await apiPost<{ path: string }>('/files/select-directory');
    if (result.path) {
      updateNodeParam(node.id, name, result.path);
    }
  };

  return (
    <div className="w-72 bg-[#202124] border-l border-[#0f0f10] flex flex-col flex-shrink-0 overflow-y-auto shadow-[inset_1px_0_0_#2f3033]">
      {/* Header */}
      <div className="p-3 border-b border-[#111]">
        <div className="flex items-center justify-between">
          <div className="text-xs font-bold text-[#f2f2f2] truncate">{node.label}</div>
          <button onClick={() => setSelectedNodeId(null)} className="h-6 w-6 rounded bg-[#2a2b2f] text-[#9c9da2] hover:bg-[#36373c]">x</button>
        </div>
        <div className="text-[10px] text-[#8f9095]">{node.type}</div>
        <div className={`text-[10px] mt-1 ${
          node.status === 'done' ? 'text-[#6cc08d]' :
          node.status === 'running' ? 'text-[var(--accent)]' :
          node.status === 'failed' ? 'text-[#ff7777]' : 'text-[#8f9095]'
        }`}>
          {node.status}
          {node.error && <span className="text-[#ff7777] ml-1">- {node.error.slice(0, 60)}</span>}
        </div>
        {validationIssues.length > 0 && (
          <div className="mt-2 rounded border border-[#6f3434] bg-[#261819] p-2 text-[10px] text-[#ff9a9a]">
            {validationIssues[0].message}
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex border-b border-[#111] bg-[#1a1b1d]">
        {(['params', 'inputs', 'outputs', 'logs'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 py-1.5 text-[10px] ${
              tab === t ? 'text-[var(--accent)] border-b border-[var(--accent)] bg-[#202124]' : 'text-[#8f9095]'
            }`}
          >
            {{ params: tr(language, 'detail.params'), inputs: tr(language, 'detail.inputs'), outputs: tr(language, 'detail.outputs'), logs: tr(language, 'detail.logs') }[t]}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="p-3 flex-1">
        {validationIssues.length > 0 && (
          <div className="mb-3 space-y-1 rounded border border-[#6f3434] bg-[#1f1516] p-2 text-[10px] text-[#ffb0b0]">
            {validationIssues.map((issue, index) => (
              <div key={`${issue.code}-${issue.field || ''}-${index}`}>
                <span className="font-semibold">{issue.code}</span>
                {issue.field && <span className="ml-1 text-[#d98a8a]">{issue.field}</span>}
                <div className="mt-0.5 text-[#f0b4b4]">{issue.message}</div>
              </div>
            ))}
          </div>
        )}
        {tab === 'params' && Object.entries(node.params).map(([name, spec]) => {
          const options = paramOptions(name, spec);
          return (
          <div key={name} className="mb-3">
            <div className="text-[10px] text-[#a7a7a7] mb-1">
              {name}
              {spec.required && <span className="ml-1 text-[#ff8c8c]">*</span>}
            </div>
            {name === 'draft_folder' ? (
              <button
                type="button"
                onClick={() => chooseDirectoryParam(name).catch(console.error)}
                className="w-full truncate rounded border border-[#3c3d42] bg-[#151617] px-2 py-1.5 text-left text-xs text-[#f2f2f2] outline-none hover:border-[var(--accent)]"
              >
                {pvs[name] !== undefined ? pvs[name] : spec.default || (language === 'zh' ? '选择目录' : 'Choose folder')}
              </button>
            ) : options ? (
              <select
                value={spec.param_type === 'bool' ? String(Boolean(pvs[name] !== undefined ? pvs[name] : spec.default)) : pvs[name] !== undefined ? pvs[name] : spec.default ?? ''}
                onChange={(e) => updateNodeParam(node.id, name, spec.param_type === 'bool' ? e.target.value === 'true' : e.target.value)}
                className="w-full bg-[#151617] border border-[#3c3d42] rounded px-2 py-1.5 text-xs text-[#f2f2f2] outline-none focus:border-[var(--accent)]"
              >
                {options.map((option: string) => (
                  <option key={String(option)} value={String(option)}>
                    {spec.param_type === 'bool' && language === 'zh' ? option === 'true' ? '开启' : '关闭' : String(option)}
                  </option>
                ))}
              </select>
            ) : (
              <input
                type={spec.param_type === 'int' || spec.param_type === 'float' ? 'number' : 'text'}
                value={pvs[name] !== undefined ? pvs[name] : spec.default ?? ''}
                onChange={(e) => {
                  const val = spec.param_type === 'float' || spec.param_type === 'int'
                    ? Number(e.target.value)
                    : e.target.value;
                  updateNodeParam(node.id, name, val);
                }}
                className="w-full bg-[#151617] border border-[#3c3d42] rounded px-2 py-1.5 text-xs text-[#f2f2f2] outline-none focus:border-[var(--accent)]"
              />
            )}
            {spec.description && <div className="text-[10px] text-[#77787d] mt-0.5">{spec.description}</div>}
          </div>
          );
        })}
        {tab === 'inputs' && Object.entries(node.inputs).map(([name, spec]) => (
          <div key={name} className="mb-2 text-xs">
            <span className="text-[#c7c8cc]">{name}</span>
            <span className="text-[#77787d] ml-1">({spec.port_type})</span>
            {!spec.required && <span className="text-[#77787d] ml-1">{tr(language, 'detail.optional')}</span>}
          </div>
        ))}
        {tab === 'outputs' && (
          <>
            {Object.entries(node.outputs).map(([name, spec]) => (
              <div key={name} className="mb-2 text-xs">
                <span className="text-[#d7b36b]">{name}</span>
                <span className="text-[#77787d] ml-1">({spec.port_type})</span>
                {node.outputs_cache && node.outputs_cache[name] && (
                  <div className="text-[10px] text-[#6cc08d] mt-0.5 truncate">{String(node.outputs_cache[name])}</div>
                )}
              </div>
            ))}
            {Object.keys(node.outputs).length === 0 && (
              <div className="text-[10px] text-[#77787d]">{tr(language, 'detail.noOutputs')}</div>
            )}
          </>
        )}
        {tab === 'logs' && (
          <div className="space-y-2 text-[10px] text-[#77787d]">
            {logs.length > 0 ? (
              logs.map((entry, index) => (
                <div key={`${entry.created_at || ''}-${index}`} className="rounded border border-[#33343a] bg-[#151617] p-2">
                  <div className={entry.level === 'error' ? 'mb-1 font-semibold text-[#ff7777]' : 'mb-1 font-semibold text-[#9cbcff]'}>
                    {entry.level}
                    {entry.created_at && <span className="ml-2 font-normal text-[#77787d]">{new Date(entry.created_at).toLocaleTimeString()}</span>}
                  </div>
                  <pre className="log-text max-h-96 overflow-auto whitespace-pre-wrap break-words font-mono text-[10px] leading-4 text-[#d7d7d7]">
                    {entry.message}
                  </pre>
                </div>
              ))
            ) : node.status === 'failed' && node.error ? (
              <pre className="log-text overflow-auto whitespace-pre-wrap break-words rounded border border-[#4a2b2b] bg-[#1d1515] p-2 font-mono text-[10px] leading-4 text-[#ff7777]">
                {node.error}
              </pre>
            ) : (
              <div>{tr(language, 'detail.noLogs')}</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
