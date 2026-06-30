import { useCallback, useEffect, useState } from 'react';
import { useStore } from '../stores/useStore';
import { apiPost, apiGet, apiPut, createWs } from '../api/client';
import type { Task } from '../types';
import { nodeLabel, t, type Language } from '../i18n';

export default function TopBar() {
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'failed'>('idle');
  const [editingName, setEditingName] = useState(false);
  const [draftName, setDraftName] = useState('');
  const {
    running,
    setRunning,
    nodes,
    edges,
    activeTemplateId,
    workflowName,
    executingNodeId,
    setWorkflowName,
    setCurrentTaskId,
    setTasks,
    setTemplates,
    setActiveTemplateId,
    language,
    setLanguage,
  } = useStore();
  const currentNode = nodes.find((node) => node.id === executingNodeId)
    || nodes.find((node) => node.status === 'running');
  const currentNodePrefix = running
    ? (language === 'zh' ? '当前节点' : 'Current')
    : currentNode?.status === 'failed'
      ? (language === 'zh' ? '失败节点' : 'Failed')
      : (language === 'zh' ? '最后节点' : 'Last');

  const buildGraphJson = useCallback(() => {
    const graphNodes = useStore.getState().nodes;
    const graphEdges = useStore.getState().edges;
    return JSON.stringify({
      nodes: graphNodes.map((n) => ({
        id: n.id, type: n.type, label: n.label,
        x: n.x, y: n.y, status: 'idle',
        inputs: n.inputs,
        outputs: n.outputs,
        params: Object.fromEntries(Object.entries(n.params).map(([k, v]) => {
          const pv = n.paramValues || {};
          const spec = v as any;
          return [k, { ...spec, default: pv[k] !== undefined ? pv[k] : spec.default }];
        })),
      })),
      edges: graphEdges,
    });
  }, []);

  const displayName = workflowName || activeTemplateId || t(language, 'top.noWorkflow');

  const handleSave = useCallback(async () => {
    if (saveStatus === 'saving') return;
    setSaveStatus('saving');
    try {
      const graph_json = buildGraphJson();
      const existingTemplate = useStore.getState().templates.find((template) => template.id === activeTemplateId);
      const name = workflowName || existingTemplate?.name || activeTemplateId || `Workflow ${new Date().toLocaleString()}`;
      const description = existingTemplate?.description || '';
      let saved: { id: string; name: string };

      if (activeTemplateId) {
        saved = await apiPut<{ id: string; name: string }>(`/templates/${activeTemplateId}`, { name, description, graph_json });
      } else {
        saved = await apiPost<{ id: string; name: string }>('/templates', {
          name,
          description,
          graph_json,
        });
      }

      setActiveTemplateId(saved.id);
      const templates = await apiGet<any[]>('/templates');
      setTemplates(templates);
      setSaveStatus('saved');
      window.setTimeout(() => setSaveStatus('idle'), 1600);
    } catch (error) {
      console.error('save failed:', error);
      setSaveStatus('failed');
      window.setTimeout(() => setSaveStatus('idle'), 2200);
    }
  }, [
    activeTemplateId,
    buildGraphJson,
    saveStatus,
    setActiveTemplateId,
    setTemplates,
    workflowName,
  ]);

  const startRename = () => {
    setDraftName(displayName);
    setEditingName(true);
  };

  const commitRename = async () => {
    const nextName = draftName.trim();
    setEditingName(false);
    if (!nextName || nextName === displayName) return;
    setWorkflowName(nextName);

    if (!activeTemplateId) return;
    try {
      const graph_json = buildGraphJson();
      const existingTemplate = useStore.getState().templates.find((template) => template.id === activeTemplateId);
      await apiPut(`/templates/${activeTemplateId}`, { name: nextName, description: existingTemplate?.description || '', graph_json });
      const templates = await apiGet<any[]>('/templates');
      setTemplates(templates);
    } catch (error) {
      console.error('rename failed:', error);
    }
  };

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
        event.preventDefault();
        handleSave();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [handleSave]);

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
    useStore.getState().setExecutingNodeId(null);
    try {
      const { task_id } = await apiPost<{ task_id: string }>('/graph/run', {
        graph_json: JSON.stringify(graph),
        task_name: 'New Task',
      });
      setCurrentTaskId(task_id);

      let finished = false;
      let pollTimer: number | undefined;
      let ws: WebSocket | null = null;

      const applyTaskSnapshot = (task: Task) => {
        const state = useStore.getState();
        if (task.current_node_id) {
          state.setExecutingNodeId(task.current_node_id);
          if (task.status === 'running') {
            state.updateNodeStatus(task.current_node_id, 'running');
          } else if (task.status === 'failed') {
            state.updateNodeStatus(task.current_node_id, 'failed', task.error);
          }
        }
        try {
          const result = JSON.parse(task.result_json || '{}');
          if (Array.isArray(result.node_results)) {
            state.applyNodeResults(result.node_results);
          }
        } catch {}
      };

      const stopPolling = () => {
        if (pollTimer !== undefined) {
          window.clearInterval(pollTimer);
          pollTimer = undefined;
        }
      };

      const finishFromTask = (task?: Task) => {
        if (finished) return;
        finished = true;
        if (task) applyTaskSnapshot(task);
        stopPolling();
        setRunning(false);
        ws?.close();
        apiGet<any[]>('/tasks').then((tasks) => setTasks(tasks));
      };

      const refreshTaskSnapshot = async () => {
        const task = await apiGet<Task>(`/tasks/${task_id}`);
        applyTaskSnapshot(task);
        if (task.status === 'done' || task.status === 'failed') {
          finishFromTask(task);
        }
      };

      pollTimer = window.setInterval(() => {
        refreshTaskSnapshot().catch(() => {});
      }, 700);

      ws = createWs(task_id, (event) => {
        if (event.type === 'node_executing') {
          const state = useStore.getState();
          state.setExecutingNodeId(event.node_id);
          state.updateNodeStatus(event.node_id, 'running');
        } else if (event.type === 'node_status') {
          const state = useStore.getState();
          state.updateNodeStatus(event.node_id, event.data.status);
        } else if (event.type === 'node_done') {
          const state = useStore.getState();
          state.updateNodeStatus(event.node_id, 'done', undefined, event.data.outputs);
        } else if (event.type === 'node_error') {
          const state = useStore.getState();
          state.updateNodeStatus(event.node_id, 'failed', event.data.error, undefined, event.data.validation_issues || []);
          state.setExecutingNodeId(event.node_id);
        } else if (event.type === 'log' && event.node_id) {
          useStore.getState().appendNodeLog(event.node_id, event.data.level || 'info', event.data.message || '');
        } else if (event.type === 'graph_complete' || event.type === 'graph_error') {
          if (event.type === 'graph_error') {
            useStore.getState().setExecutingNodeId(null);
          }
          apiGet<Task>(`/tasks/${task_id}`).then((task) => {
            finishFromTask(task);
          }).catch(() => finishFromTask());
        }
      });
    } catch (e) {
      console.error('run failed:', e);
      setRunning(false);
    }
  };

  return (
    <div className="topbar h-12 flex items-center px-3 gap-2 flex-shrink-0">
      <div className="topbar-title h-7 px-3 rounded flex items-center gap-2">
        <span className="text-xs font-semibold">{t(language, 'app.title')}</span>
        <span className="opacity-40">/</span>
        {editingName ? (
          <input
            autoFocus
            value={draftName}
            onChange={(event) => setDraftName(event.target.value)}
            onBlur={commitRename}
            onKeyDown={(event) => {
              if (event.key === 'Enter') commitRename();
              if (event.key === 'Escape') {
                setEditingName(false);
                setDraftName(displayName);
              }
            }}
            className="topbar-title-input h-5 w-44 rounded px-1 text-xs outline-none"
          />
        ) : (
          <button
            onClick={startRename}
            className="max-w-56 truncate text-xs font-semibold hover:underline"
            aria-label={language === 'zh' ? '点击重命名工作流' : 'Click to rename workflow'}
          >
            {displayName}
          </button>
        )}
      </div>
      <button
        onClick={handleRun}
        disabled={running || nodes.length === 0}
        className={`h-7 px-4 text-xs rounded border font-medium transition-colors ${
          running
            ? 'bg-[#3a3b3f] border-[#505158] text-[#8c8d93] cursor-not-allowed'
            : 'bg-[var(--accent)] hover:brightness-110 border-[var(--accent)] text-[var(--accent-contrast)]'
        }`}
      >
        {running ? t(language, 'top.queueRunning') : t(language, 'top.queuePrompt')}
      </button>
      {currentNode && (
        <div className={`topbar-running-node ${running ? 'running' : 'last'}`}>
          <span className="topbar-running-dot" />
          <span className="truncate">
            {currentNodePrefix}: {nodeLabel(language, currentNode.type, currentNode.label, currentNode.id)}
          </span>
        </div>
      )}
      <button
        onClick={handleSave}
        disabled={saveStatus === 'saving'}
        className="topbar-button h-7 px-3 text-xs rounded border"
      >
        {saveStatus === 'saving' ? 'Saving...' : saveStatus === 'saved' ? 'Saved' : saveStatus === 'failed' ? 'Save failed' : t(language, 'top.save')}
      </button>
      <div className="flex-1" />
      <label className="flex items-center gap-1 text-[10px] opacity-75">
        <span>{t(language, 'top.language')}</span>
        <select
          value={language}
          onChange={(event) => setLanguage(event.target.value as Language)}
          className="topbar-select h-7 rounded border px-2 text-xs outline-none"
        >
          <option value="zh">中文</option>
          <option value="en">English</option>
        </select>
      </label>
      <span className="text-[10px] opacity-75">
        {activeTemplateId || t(language, 'top.noWorkflow')} · {nodes.length} {t(language, 'top.nodes')} · {edges.length} {t(language, 'top.links')}
      </span>
    </div>
  );
}
