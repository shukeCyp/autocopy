import { useEffect, useMemo, useState } from 'react';
import type React from 'react';
import {
  ApartmentOutlined,
  AudioOutlined,
  BranchesOutlined,
  CloseOutlined,
  CopyOutlined,
  DeleteOutlined,
  EditOutlined,
  ExportOutlined,
  FolderOpenOutlined,
  HistoryOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  MoonOutlined,
  NodeIndexOutlined,
  ScissorOutlined,
  SettingOutlined,
  SoundOutlined,
  SunOutlined,
  VideoCameraOutlined,
} from '@ant-design/icons';
import { useStore } from '../stores/useStore';
import { apiGet, apiPost, apiDelete } from '../api/client';
import type { Task, Template, NodeData, EdgeData } from '../types';
import { nodeLabel, t as tr } from '../i18n';

type DrawerTab = 'workflows' | 'tasks' | 'nodes' | 'settings';

const TAB_META: Record<DrawerTab, { icon: React.ReactNode; zh: string; en: string }> = {
  workflows: { icon: <ApartmentOutlined />, zh: '工作流', en: 'Workflows' },
  tasks: { icon: <HistoryOutlined />, zh: '任务记录', en: 'Tasks' },
  nodes: { icon: <NodeIndexOutlined />, zh: '节点库', en: 'Nodes' },
  settings: { icon: <SettingOutlined />, zh: '设置', en: 'Settings' },
};

const NODE_TYPES = ['VideoInput', 'TTSExtract', 'SRTRewrite', 'VideoMatch', 'TTSGenerate', 'VideoCompose', 'JianyingExport'];

const NODE_TYPE_ICONS: Record<string, React.ReactNode> = {
  VideoInput: <VideoCameraOutlined />,
  TTSExtract: <AudioOutlined />,
  SRTRewrite: <EditOutlined />,
  VideoMatch: <BranchesOutlined />,
  TTSGenerate: <SoundOutlined />,
  VideoCompose: <ScissorOutlined />,
  JianyingExport: <ExportOutlined />,
};

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const [activeTab, setActiveTab] = useState<DrawerTab>('workflows');
  const [loadingTemplateId, setLoadingTemplateId] = useState<string | null>(null);
  const [creatingWorkflow, setCreatingWorkflow] = useState(false);
  const [workflowMenu, setWorkflowMenu] = useState<{ template: Template; x: number; y: number } | null>(null);
  const [sidebarError, setSidebarError] = useState<string>('');
  const {
    tasks,
    currentTaskId,
    setTasks,
    setCurrentTaskId,
    setGraph,
    replaceGraph,
    templates,
    activeTemplateId,
    setTemplates,
    nodes,
    edges,
    language,
    setLanguage,
    theme,
    setTheme,
  } = useStore();

  const label = (tab: DrawerTab) => language === 'zh' ? TAB_META[tab].zh : TAB_META[tab].en;

  const refreshTemplates = async () => {
    const refreshed = await apiGet<Template[]>('/templates');
    setTemplates(refreshed);
    return refreshed;
  };

  useEffect(() => {
    refreshTemplates()
      .then((data) => {
        setTemplates(data);
        setSidebarError('');
      })
      .catch(() => setSidebarError(tr(language, 'sidebar.templatesLoadFailed')));
  }, [language, setTemplates]);

  useEffect(() => {
    apiGet<Task[]>('/tasks').then(setTasks).catch(() => {});
  }, [setTasks]);

  const templateNodeSamples = useMemo(() => {
    const samples = new Map<string, NodeData>();
    for (const template of templates) {
      if (!template.graph_json) continue;
      try {
        const graph = JSON.parse(template.graph_json);
        for (const node of graph.nodes || []) {
          if (!samples.has(node.type)) samples.set(node.type, node);
        }
      } catch {}
    }
    return samples;
  }, [templates]);

  const loadTemplate = async (template: Template) => {
    setLoadingTemplateId(template.id);
    setSidebarError('');
    try {
      const data = template.graph_json
        ? (template as Template & { graph_json: string })
        : await apiGet<Template & { graph_json: string }>(`/templates/${template.id}`);
      const graph = JSON.parse(data.graph_json || '{}');
      const newNodes: NodeData[] = (graph.nodes || []).map((node: any) => ({
        ...node,
        status: 'idle' as const,
        paramValues: {},
      }));
      const newEdges: EdgeData[] = (graph.edges || []).map((edge: any) => ({
        source_node_id: edge.source_node_id,
        source_port: edge.source_port,
        target_node_id: edge.target_node_id,
        target_port: edge.target_port,
      }));
      replaceGraph(newNodes, newEdges, template.id, template.builtin, template.name);
      setCurrentTaskId(null);
    } catch (error) {
      console.error('load template failed:', error);
      setSidebarError(`${tr(language, 'sidebar.templateLoadFailed')}：${template.name}`);
    } finally {
      setLoadingTemplateId(null);
    }
  };

  const createBlankWorkflow = async () => {
    if (creatingWorkflow) return;
    setCreatingWorkflow(true);
    setSidebarError('');
    const name = language === 'zh' ? '未命名工作流' : 'Untitled Workflow';
    const graph_json = JSON.stringify({ nodes: [], edges: [] });
    try {
      const saved = await apiPost<{ id: string; name: string }>('/templates', { name, graph_json });
      replaceGraph([], [], saved.id, false, saved.name);
      setCurrentTaskId(null);
      await refreshTemplates();
    } catch (error) {
      console.error('create workflow failed:', error);
      setSidebarError(tr(language, 'sidebar.workflowCreateFailed'));
    } finally {
      setCreatingWorkflow(false);
    }
  };

  const copyWorkflow = async (template: Template) => {
    setWorkflowMenu(null);
    setSidebarError('');
    try {
      const data = template.graph_json
        ? (template as Template & { graph_json: string })
        : await apiGet<Template & { graph_json: string }>(`/templates/${template.id}`);
      const saved = await apiPost<{ id: string; name: string }>('/templates', {
        name: `${template.name} Copy`,
        graph_json: data.graph_json,
      });
      await refreshTemplates();
      await loadTemplate({ ...template, id: saved.id, name: saved.name, builtin: false, graph_json: data.graph_json });
    } catch (error) {
      console.error('copy workflow failed:', error);
      setSidebarError(tr(language, 'sidebar.workflowCopyFailed'));
    }
  };

  const deleteWorkflow = async (template: Template) => {
    setWorkflowMenu(null);
    if (template.builtin) return;
    setSidebarError('');
    try {
      await apiDelete(`/templates/${template.id}`);
      if (activeTemplateId === template.id) {
        replaceGraph([], [], null, false, '');
        setCurrentTaskId(null);
      }
      await refreshTemplates();
    } catch (error) {
      console.error('delete workflow failed:', error);
      setSidebarError(tr(language, 'sidebar.workflowDeleteFailed'));
    }
  };

  const loadTask = async (task: Task) => {
    setCurrentTaskId(task.id);
    try {
      const data = await apiGet<Task & { graph_json: string }>(`/tasks/${task.id}`);
      const graph = JSON.parse(typeof data.graph_json === 'string' ? data.graph_json : JSON.stringify(data.graph_json));
      replaceGraph(
        (graph.nodes || []).map((node: any) => ({ ...node, paramValues: node.paramValues || {} })),
        (graph.edges || []).map((edge: any) => ({
          source_node_id: edge.source_node_id,
          source_port: edge.source_port,
          target_node_id: edge.target_node_id,
          target_port: edge.target_port,
        })),
        null,
        false,
        task.name || task.id
      );
    } catch {}
  };

  const deleteTask = async (id: string, event: React.MouseEvent) => {
    event.stopPropagation();
    await apiDelete(`/tasks/${id}`);
    if (currentTaskId === id) {
      setCurrentTaskId(null);
      setGraph([], []);
    }
    apiGet<Task[]>('/tasks').then(setTasks).catch(() => {});
  };

  const addNode = (nodeType: string) => {
    const sample = templateNodeSamples.get(nodeType);
    const base: NodeData = sample
      ? JSON.parse(JSON.stringify(sample))
      : {
          id: nodeType,
          type: nodeType,
          label: nodeType,
          x: 160,
          y: 160,
          status: 'idle',
          inputs: {},
          outputs: {},
          params: {},
        };
    const id = `${nodeType.toLowerCase()}_${Date.now().toString(36)}`;
    const nextNode: NodeData = {
      ...base,
      id,
      x: 160 + nodes.length * 28,
      y: 120 + nodes.length * 28,
      status: 'idle',
      error: undefined,
      outputs_cache: undefined,
      paramValues: {},
    };
    setGraph([...nodes, nextNode], edges);
  };

  const renderWorkflows = () => (
    <div className="drawer-panel-scroll" onClick={() => setWorkflowMenu(null)}>
      <div className="drawer-section-head">
        <span>{tr(language, 'sidebar.workflows')}</span>
        <span className="drawer-section-actions">
          <button className="drawer-small-button primary" onClick={createBlankWorkflow} disabled={creatingWorkflow}>
            {creatingWorkflow ? tr(language, 'sidebar.loading') : tr(language, 'sidebar.newWorkflow')}
          </button>
        </span>
      </div>
      {sidebarError && <div className="drawer-error">{sidebarError}</div>}
      {templates.map((template) => (
        <button
          key={template.id}
          onClick={() => loadTemplate(template)}
          onContextMenu={(event) => {
            event.preventDefault();
            setWorkflowMenu({ template, x: event.clientX, y: event.clientY });
          }}
          disabled={loadingTemplateId !== null}
          className={`drawer-list-item ${activeTemplateId === template.id ? 'active' : ''}`}
        >
          <span className="drawer-list-icon workflow-icon"><ApartmentOutlined /></span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-xs font-semibold">{loadingTemplateId === template.id ? tr(language, 'sidebar.loading') : template.name}</span>
            <span className="block truncate text-[10px] opacity-65">
              {template.builtin ? `${tr(language, 'sidebar.builtin')} · ` : ''}{template.id === 'tts_only' ? tr(language, 'sidebar.ttsOnly') : tr(language, 'sidebar.fullFlow')}
            </span>
          </span>
        </button>
      ))}
      {workflowMenu && (
        <div
          className="drawer-context-menu"
          style={{ left: workflowMenu.x, top: workflowMenu.y }}
          onClick={(event) => event.stopPropagation()}
        >
          <button onClick={() => loadTemplate(workflowMenu.template)}>
            <FolderOpenOutlined />
            <span>{tr(language, 'context.open')}</span>
          </button>
          <button onClick={() => copyWorkflow(workflowMenu.template)}>
            <CopyOutlined />
            <span>{tr(language, 'context.duplicate')}</span>
          </button>
          <button
            className="danger"
            disabled={workflowMenu.template.builtin}
            onClick={() => deleteWorkflow(workflowMenu.template)}
          >
            <DeleteOutlined />
            <span>{tr(language, 'context.delete')}</span>
          </button>
        </div>
      )}
    </div>
  );

  const renderTasks = () => (
    <div className="drawer-panel-scroll">
      <div className="drawer-section-head"><span>{tr(language, 'sidebar.tasks')}</span></div>
      {tasks.map((task) => (
        <button
          key={task.id}
          onClick={() => loadTask(task)}
          className={`drawer-list-item group ${currentTaskId === task.id ? 'active' : ''}`}
        >
          <span className="min-w-0 flex-1">
            <span className="block truncate text-xs font-semibold">{task.name || task.id.slice(0, 16)}</span>
            <span className={`block text-[10px] ${task.status === 'failed' ? 'text-red-400' : task.status === 'done' ? 'text-green-400' : 'opacity-65'}`}>
              {task.status}
            </span>
          </span>
          <span
            role="button"
            tabIndex={0}
            onClick={(event) => deleteTask(task.id, event as any)}
            className="drawer-delete"
          >
            <DeleteOutlined />
          </span>
        </button>
      ))}
      {tasks.length === 0 && <div className="drawer-empty">{tr(language, 'sidebar.emptyTasks')}</div>}
    </div>
  );

  const renderNodes = () => (
    <div className="drawer-panel-scroll">
      <div className="drawer-section-head"><span>{label('nodes')}</span></div>
      {NODE_TYPES.map((nodeType) => (
        <button key={nodeType} className="drawer-list-item" onClick={() => addNode(nodeType)}>
          <span className="drawer-list-icon">{NODE_TYPE_ICONS[nodeType] || <NodeIndexOutlined />}</span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-xs font-semibold">{nodeLabel(language, nodeType, nodeType)}</span>
            <span className="block truncate text-[10px] opacity-65">{nodeType}</span>
          </span>
        </button>
      ))}
    </div>
  );

  const renderSettings = () => (
    <div className="drawer-panel-scroll">
      <div className="drawer-section-head"><span>{label('settings')}</span></div>
      <label className="drawer-setting-row">
        <span>{language === 'zh' ? '语言' : 'Language'}</span>
        <select value={language} onChange={(event) => setLanguage(event.target.value as any)}>
          <option value="zh">中文</option>
          <option value="en">English</option>
        </select>
      </label>
      <label className="drawer-setting-row">
        <span>{language === 'zh' ? '主题' : 'Theme'}</span>
        <select value={theme} onChange={(event) => setTheme(event.target.value as any)}>
          <option value="dark">{language === 'zh' ? '黑夜' : 'Dark'}</option>
          <option value="light">{language === 'zh' ? '白天' : 'Light'}</option>
        </select>
      </label>
    </div>
  );

  const panel = {
    workflows: renderWorkflows,
    tasks: renderTasks,
    nodes: renderNodes,
    settings: renderSettings,
  }[activeTab]();

  return (
    <aside className={`drawer ${collapsed ? 'collapsed' : ''}`}>
      <div className="drawer-rail">
        <button
          className="drawer-toggle"
          aria-label={collapsed ? (language === 'zh' ? '展开抽屉' : 'Expand drawer') : (language === 'zh' ? '收起抽屉' : 'Collapse drawer')}
          onClick={() => setCollapsed(!collapsed)}
        >
          {collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
        </button>
        {(Object.keys(TAB_META) as DrawerTab[]).map((tab) => (
          <button
            key={tab}
            aria-label={label(tab)}
            onClick={() => {
              setActiveTab(tab);
              if (collapsed) setCollapsed(false);
            }}
            className={`drawer-rail-button ${activeTab === tab ? 'active' : ''}`}
          >
            {TAB_META[tab].icon}
          </button>
        ))}
        <button className="drawer-rail-button mt-auto" aria-label={theme === 'dark' ? 'Light' : 'Dark'} onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>
          {theme === 'dark' ? <MoonOutlined /> : <SunOutlined />}
        </button>
      </div>
      {!collapsed && (
        <div className="drawer-panel">
          <div className="drawer-panel-title">
            <span>{label(activeTab)}</span>
            <button onClick={() => setCollapsed(true)}><CloseOutlined /></button>
          </div>
          {panel}
        </div>
      )}
    </aside>
  );
}
