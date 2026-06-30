import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ReactFlow, {
  Background, Controls,
  useNodesState, useEdgesState, addEdge, applyNodeChanges, applyEdgeChanges,
} from 'reactflow';
import type { Connection, Node, Edge, NodeChange, EdgeChange, ReactFlowInstance, OnConnectStartParams } from 'reactflow';
import 'reactflow/dist/style.css';

import { useStore } from '../stores/useStore';
import { apiGet } from '../api/client';
import PipelineNode from './custom/PipelineNode';
import type { Template, NodeData, EdgeData } from '../types';
import { nodeLabel, t } from '../i18n';
import { loadNodeSpecMap } from '../nodeSpecs';

const nodeTypes = { pipeline: PipelineNode };

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

function portColor(portType?: string, portName?: string) {
  return (portName && PORT_NAME_COLORS[portName]) || PORT_COLORS[portType || ''] || '#8b8c90';
}

export default function Canvas() {
  const [contextMenu, setContextMenu] = useState<{ nodeId: string; x: number; y: number } | null>(null);
  const [nodeSearch, setNodeSearch] = useState<{ x: number; y: number; flowX: number; flowY: number } | null>(null);
  const [nodeSearchQuery, setNodeSearchQuery] = useState('');
  const [nodeSearchPreview, setNodeSearchPreview] = useState<NodeData | null>(null);
  const reconnectStartRef = useRef<{ nodeId: string; handleId: string } | null>(null);
  const reconnectCompletedRef = useRef(false);
  const searchInputRef = useRef<HTMLInputElement | null>(null);
  const {
    nodes: graphNodes,
    edges: graphEdges,
    graphVersion,
    selectedNodeId,
    executingNodeId,
    setGraph,
    replaceGraph,
    setSelectedNodeId,
    running,
    language,
  } = useStore();
  const [flowInstance, setFlowInstance] = useState<ReactFlowInstance | null>(null);
  const [templateNodeSamples, setTemplateNodeSamples] = useState<Map<string, NodeData>>(new Map());

  // Load backend node schemas first, with built-in frontend specs as fallback.
  useEffect(() => {
    let cancelled = false;

    async function loadCanvasSources() {
      const [templates, samples] = await Promise.all([
        apiGet<Template[]>('/templates').catch(() => []),
        loadNodeSpecMap(),
      ]);
      if (cancelled) return;

        for (const template of templates) {
          if (!template.graph_json) continue;
          try {
            const graph = JSON.parse(template.graph_json);
            for (const node of graph.nodes || []) {
              if (!samples.has(node.type)) samples.set(node.type, node);
            }
          } catch {}
        }
        setTemplateNodeSamples(samples);

        const state = useStore.getState();
        if (state.nodes.length === 0 && !state.workflowName && !state.activeTemplateId && templates.length > 0) {
          const t = templates[0];
          apiGet<Template & { graph_json: string }>(`/templates/${t.id}`).then((data) => {
            if (cancelled) return;
            const g = JSON.parse(data.graph_json || '{}');
            const latest = useStore.getState();
            if (latest.nodes.length === 0 && !latest.workflowName && !latest.activeTemplateId) {
              const newNodes: NodeData[] = (g.nodes || []).map((n: any) => ({
                ...n, status: 'idle' as const, paramValues: {}, validationIssues: [],
              }));
              const newEdges: EdgeData[] = (g.edges || []).map((e: any) => ({
                source_node_id: e.source_node_id, source_port: e.source_port,
                target_node_id: e.target_node_id, target_port: e.target_port,
              }));
              replaceGraph(newNodes, newEdges, t.id, t.name);
            }
          }).catch(() => {});
        }
    }

    loadCanvasSources();
    return () => {
      cancelled = true;
    };
  }, [replaceGraph]);

  const nodeSearchResults = useMemo(() => {
    const query = nodeSearchQuery.trim().toLowerCase();
    return Array.from(templateNodeSamples.values())
      .filter((node) => {
        if (!query) return true;
        return (
          node.type.toLowerCase().includes(query) ||
          node.label.toLowerCase().includes(query) ||
          nodeLabel(language, node.type, node.label, node.id).toLowerCase().includes(query)
        );
      })
      .slice(0, 12);
  }, [templateNodeSamples, nodeSearchQuery, language]);

  useEffect(() => {
    if (!nodeSearch) return;
    const frame = requestAnimationFrame(() => searchInputRef.current?.focus());
    return () => cancelAnimationFrame(frame);
  }, [nodeSearch]);

  const rfNodes: Node[] = graphNodes.map((n) => ({
    id: n.id,
    type: 'pipeline',
    position: { x: n.x || 0, y: n.y || 0 },
    selected: selectedNodeId === n.id,
    data: {
      id: n.id,
      label: n.label,
      nodeType: n.type,
      status: n.status || 'idle',
      language,
      inputs: n.inputs,
      outputs: n.outputs,
      params: n.params,
      paramValues: n.paramValues || {},
      outputs_cache: n.outputs_cache,
      error: n.error,
      validationIssues: n.validationIssues || [],
      executing: running && executingNodeId === n.id,
    },
  }));

  const rfEdges: Edge[] = graphEdges.map((e, i) => {
    const sourceNode = graphNodes.find((node) => node.id === e.source_node_id);
    const targetNode = graphNodes.find((node) => node.id === e.target_node_id);
    const portType =
      sourceNode?.outputs?.[e.source_port]?.port_type ||
      targetNode?.inputs?.[e.target_port]?.port_type ||
      'file_path';
    const stroke = portColor(portType, e.source_port || e.target_port);

    return {
      id: `${e.source_node_id}-${e.source_port}-${e.target_node_id}-${e.target_port}-${i}`,
      source: e.source_node_id,
      target: e.target_node_id,
      sourceHandle: e.source_port,
      targetHandle: e.target_port,
      animated: running,
      style: { stroke, strokeWidth: 4 },
    };
  });

  const [nodesState, setNodesState] = useNodesState(rfNodes);
  const [edgesState, setEdgesState] = useEdgesState(rfEdges);
  const activeNode = graphNodes.find((node) => node.id === executingNodeId);
  const runningNode = running
    ? activeNode || graphNodes.find((node) => node.status === 'running')
    : null;

  useEffect(() => {
    setNodesState(rfNodes);
  }, [graphNodes, selectedNodeId, executingNodeId, language]);

  useEffect(() => {
    setEdgesState(rfEdges);
  }, [graphEdges, running]);

  const handleNodesChange = useCallback(
    (changes: NodeChange[]) => {
      setNodesState((currentNodes) => applyNodeChanges(changes, currentNodes));

      const removedIds = new Set(
        changes
          .filter((change) => change.type === 'remove')
          .map((change) => change.id)
      );
      if (removedIds.size === 0) {
        return;
      }

      const nextGraphNodes = graphNodes.filter((n) => !removedIds.has(n.id));
      const nextGraphEdges = graphEdges.filter(
        (e) => !removedIds.has(e.source_node_id) && !removedIds.has(e.target_node_id)
      );

      if (selectedNodeId && removedIds.has(selectedNodeId)) {
        setSelectedNodeId(null);
      }
      setGraph(nextGraphNodes, nextGraphEdges);
    },
    [graphNodes, graphEdges, selectedNodeId, setGraph, setNodesState, setSelectedNodeId]
  );

  const handleEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      setEdgesState((currentEdges) => applyEdgeChanges(changes, currentEdges));

      const removedIds = new Set(
        changes
          .filter((change) => change.type === 'remove')
          .map((change) => change.id)
      );
      if (removedIds.size === 0) {
        return;
      }

      const edgeIds = graphEdges.map(
        (e, i) => `${e.source_node_id}-${e.source_port}-${e.target_node_id}-${e.target_port}-${i}`
      );
      const nextGraphEdges = graphEdges.filter((_, i) => !removedIds.has(edgeIds[i]));
      setGraph(graphNodes, nextGraphEdges);
    },
    [graphNodes, graphEdges, setGraph, setEdgesState]
  );

  const onNodeDragStop = useCallback(
    (_: any, node: Node) => {
      const updated = graphNodes.map((n) =>
        n.id === node.id ? { ...n, x: node.position.x, y: node.position.y } : n
      );
      setGraph(updated, graphEdges);
    },
    [graphNodes, graphEdges, setGraph]
  );

  const onNodeDragStart = useCallback(
    (_: any, node: Node) => {
      setContextMenu(null);
      setSelectedNodeId(node.id);
    },
    [setSelectedNodeId]
  );

  const onConnect = useCallback(
    (conn: Connection) => {
      if (!conn.source || !conn.target || !conn.sourceHandle || !conn.targetHandle) return;
      reconnectCompletedRef.current = true;
      const newEdge: any = {
        source_node_id: conn.source,
        source_port: conn.sourceHandle,
        target_node_id: conn.target,
        target_port: conn.targetHandle,
      };
      const reconnectStart = reconnectStartRef.current;
      const nextEdges = reconnectStart
        ? graphEdges.filter(
            (edge) => !(edge.target_node_id === reconnectStart.nodeId && edge.target_port === reconnectStart.handleId)
          )
        : graphEdges;
      setGraph(graphNodes, [...nextEdges, newEdge]);
      setEdgesState((eds) => addEdge(conn, eds));
    },
    [graphNodes, graphEdges, setGraph, setEdgesState]
  );

  const onConnectStart = useCallback((_: any, params: OnConnectStartParams) => {
    reconnectStartRef.current = null;
    reconnectCompletedRef.current = false;
    if (params.handleType !== 'target' || !params.nodeId || !params.handleId) return;
    const incomingEdges = graphEdges.filter(
      (edge) => edge.target_node_id === params.nodeId && edge.target_port === params.handleId
    );
    if (incomingEdges.length !== 1) return;
    reconnectStartRef.current = { nodeId: params.nodeId, handleId: params.handleId };
  }, [graphEdges]);

  const onConnectEnd = useCallback(() => {
    const start = reconnectStartRef.current;
    const completed = reconnectCompletedRef.current;
    reconnectStartRef.current = null;
    reconnectCompletedRef.current = false;
    if (!start || completed) return;
    const incomingEdges = graphEdges.filter(
      (edge) => edge.target_node_id === start.nodeId && edge.target_port === start.handleId
    );
    if (incomingEdges.length !== 1) return;
    const nextEdges = graphEdges.filter(
      (edge) => !(edge.target_node_id === start.nodeId && edge.target_port === start.handleId)
    );
    setGraph(graphNodes, nextEdges);
  }, [graphNodes, graphEdges, setGraph]);

  const onNodeClick = useCallback(
    (_: any, node: Node) => {
      setContextMenu(null);
      setSelectedNodeId(node.id);
    },
    [setSelectedNodeId]
  );

  const onNodeContextMenu = useCallback(
    (event: React.MouseEvent, node: Node) => {
      event.preventDefault();
      setSelectedNodeId(node.id);
      setContextMenu({ nodeId: node.id, x: event.clientX, y: event.clientY });
    },
    [setSelectedNodeId]
  );

  const closeContextMenu = useCallback(() => setContextMenu(null), []);

  const closeNodeSearch = useCallback(() => {
    setNodeSearch(null);
    setNodeSearchQuery('');
    setNodeSearchPreview(null);
  }, []);

  const addNodeAt = useCallback((node: NodeData, x: number, y: number) => {
    const id = `${node.type.toLowerCase()}_${Date.now().toString(36)}`;
    const nextNode: NodeData = {
      ...JSON.parse(JSON.stringify(node)),
      id,
      x,
      y,
      status: 'idle',
      error: undefined,
      outputs_cache: undefined,
      paramValues: {},
    };
    setGraph([...graphNodes, nextNode], graphEdges);
    setSelectedNodeId(id);
    closeNodeSearch();
  }, [graphNodes, graphEdges, setGraph, setSelectedNodeId, closeNodeSearch]);

  const deleteNode = useCallback((nodeId: string) => {
    const nextNodes = graphNodes.filter((n) => n.id !== nodeId);
    const nextEdges = graphEdges.filter((e) => e.source_node_id !== nodeId && e.target_node_id !== nodeId);
    setGraph(nextNodes, nextEdges);
    if (selectedNodeId === nodeId) {
      setSelectedNodeId(null);
    }
    setContextMenu(null);
  }, [graphNodes, graphEdges, selectedNodeId, setGraph, setSelectedNodeId]);

  const duplicateNode = useCallback((nodeId: string) => {
    const node = graphNodes.find((n) => n.id === nodeId);
    if (!node) return;
    const copyId = `${node.id}_copy_${Date.now().toString(36)}`;
    const copy: NodeData = {
      ...node,
      id: copyId,
      label: `${node.label} copy`,
      x: (node.x || 0) + 40,
      y: (node.y || 0) + 40,
      status: 'idle',
      error: undefined,
      outputs_cache: undefined,
      paramValues: { ...(node.paramValues || {}) },
    };
    setGraph([...graphNodes, copy], graphEdges);
    setSelectedNodeId(copyId);
    setContextMenu(null);
  }, [graphNodes, graphEdges, setGraph, setSelectedNodeId]);

  const resetNodeStatus = useCallback((nodeId: string) => {
    setGraph(
      graphNodes.map((n) =>
        n.id === nodeId ? { ...n, status: 'idle', error: undefined, outputs_cache: undefined } : n
      ),
      graphEdges
    );
    setContextMenu(null);
  }, [graphNodes, graphEdges, setGraph]);

  const copyNodeId = useCallback(async (nodeId: string) => {
    try {
      await navigator.clipboard.writeText(nodeId);
    } catch {
      console.info('node id:', nodeId);
    }
    setContextMenu(null);
  }, []);

  return (
    <div className="canvas-shell flex-1 relative" onClick={closeContextMenu}>
      <div className={`canvas-status-pill ${runningNode || activeNode ? 'running' : ''}`}>
        {runningNode
          ? `${t(language, 'status.running')}: ${nodeLabel(language, runningNode.type, runningNode.label, runningNode.id)}`
          : activeNode
            ? `${activeNode.status === 'failed' ? (language === 'zh' ? '失败节点' : 'Failed') : (language === 'zh' ? '最后节点' : 'Last')}: ${nodeLabel(language, activeNode.type, activeNode.label, activeNode.id)}`
          : `${t(language, 'canvas.ready')} · ${graphNodes.length} ${t(language, 'top.nodes')} · ${graphEdges.length} ${t(language, 'top.links')}`}
      </div>
      {graphNodes.length === 0 && (
        <div className="canvas-empty-hint">
          <div>{t(language, 'canvas.emptyHint')}</div>
          <span>{t(language, 'canvas.emptySubHint')}</span>
        </div>
      )}
      <ReactFlow
        key={`graph-${graphVersion}`}
        nodes={nodesState}
        edges={edgesState}
        onNodesChange={handleNodesChange}
        onEdgesChange={handleEdgesChange}
        onNodeDragStart={onNodeDragStart}
        onNodeDragStop={onNodeDragStop}
        onConnect={onConnect}
        onConnectStart={onConnectStart}
        onConnectEnd={onConnectEnd}
        onNodeClick={onNodeClick}
        onNodeContextMenu={onNodeContextMenu}
        onPaneClick={() => {
          closeContextMenu();
          closeNodeSearch();
          setSelectedNodeId(null);
        }}
        onDoubleClick={(event: React.MouseEvent) => {
          if (!flowInstance) return;
          const target = event.target as HTMLElement;
          if (!target.classList.contains('react-flow__pane')) return;
          event.preventDefault();
          const flowPosition = flowInstance.screenToFlowPosition({ x: event.clientX, y: event.clientY });
          setNodeSearch({ x: event.clientX, y: event.clientY, flowX: flowPosition.x, flowY: flowPosition.y });
          setNodeSearchQuery('');
        }}
        onInit={setFlowInstance}
        nodeTypes={nodeTypes}
        panOnDrag
        panOnScroll
        zoomOnScroll
        zoomOnPinch
        zoomOnDoubleClick={false}
        minZoom={0.08}
        maxZoom={1.6}
        deleteKeyCode={['Backspace', 'Delete']}
        className="comfy-canvas"
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#2b2c30" gap={18} size={1} />
        <Controls />
      </ReactFlow>
      {contextMenu && (
        <div
          className="fixed z-50 min-w-40 overflow-hidden rounded border border-[#45464b] bg-[#242529] py-1 text-xs text-[#e5e5e5] shadow-2xl"
          style={{ left: contextMenu.x, top: contextMenu.y }}
          onClick={(event) => event.stopPropagation()}
        >
          <button className="block w-full px-3 py-2 text-left hover:bg-[#34353a]" onClick={() => {
            setSelectedNodeId(contextMenu.nodeId);
            setContextMenu(null);
          }}>
            {t(language, 'context.inspect')}
          </button>
          <button className="block w-full px-3 py-2 text-left hover:bg-[#34353a]" onClick={() => duplicateNode(contextMenu.nodeId)}>
            {t(language, 'context.duplicate')}
          </button>
          <button className="block w-full px-3 py-2 text-left hover:bg-[#34353a]" onClick={() => resetNodeStatus(contextMenu.nodeId)}>
            {t(language, 'context.resetStatus')}
          </button>
          <button className="block w-full px-3 py-2 text-left hover:bg-[#34353a]" onClick={() => copyNodeId(contextMenu.nodeId)}>
            {t(language, 'context.copyId')}
          </button>
          <div className="my-1 border-t border-[#3a3b40]" />
          <button className="block w-full px-3 py-2 text-left text-[#ff8989] hover:bg-[#3a2525]" onClick={() => deleteNode(contextMenu.nodeId)}>
            {t(language, 'context.delete')}
          </button>
        </div>
      )}
      {nodeSearch && (
        <div
          className="node-search-popover fixed z-50"
          onClick={(event) => event.stopPropagation()}
        >
          <div className="node-search-row">
            <input
              ref={searchInputRef}
              value={nodeSearchQuery}
              onChange={(event) => setNodeSearchQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Escape') closeNodeSearch();
                if (event.key === 'Enter' && nodeSearchResults[0]) {
                  addNodeAt(nodeSearchResults[0], nodeSearch.flowX, nodeSearch.flowY);
                }
              }}
              placeholder={language === 'zh' ? '搜索节点...' : 'Search nodes...'}
              className="node-search-input"
            />
          </div>
          <div className="node-search-list">
            {nodeSearchResults.map((node) => (
              <button
                key={node.type}
                className="node-search-item"
                onMouseEnter={() => setNodeSearchPreview(node)}
                onFocus={() => setNodeSearchPreview(node)}
                onClick={() => addNodeAt(node, nodeSearch.flowX, nodeSearch.flowY)}
              >
                <span>
                  <span className="node-search-title">{nodeLabel(language, node.type, node.label, node.id)}</span>
                  <span className="node-search-subtitle">{node.type}</span>
                </span>
                <span className="node-search-badge">TK Core</span>
              </button>
            ))}
            {nodeSearchResults.length === 0 && (
              <div className="node-search-empty">{language === 'zh' ? '没有匹配节点' : 'No matching nodes'}</div>
            )}
          </div>
          {nodeSearchPreview && (
            <div className="node-search-preview">
              <PipelineNode
                selected={false}
                data={{
                  id: `preview_${nodeSearchPreview.type}`,
                  label: nodeSearchPreview.label,
                  nodeType: nodeSearchPreview.type,
                  status: 'idle',
                  language,
                  inputs: nodeSearchPreview.inputs,
                  outputs: nodeSearchPreview.outputs,
                  params: nodeSearchPreview.params,
                  paramValues: {},
                  validationIssues: [],
                  preview: true,
                }}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
