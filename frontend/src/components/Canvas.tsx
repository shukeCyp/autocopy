import { useCallback, useEffect } from 'react';
import ReactFlow, {
  Background, Controls, MiniMap,
  useNodesState, useEdgesState, addEdge,
} from 'reactflow';
import type { Connection, Node, Edge } from 'reactflow';
import 'reactflow/dist/style.css';

import { useStore } from '../stores/useStore';
import { apiGet } from '../api/client';
import PipelineNode from './custom/PipelineNode';
import type { Template, NodeData, EdgeData } from '../types';

const nodeTypes = { pipeline: PipelineNode };

export default function Canvas() {
  const { nodes: graphNodes, edges: graphEdges, setGraph, setSelectedNodeId, running } = useStore();

  // Auto-load first template if canvas is empty
  useEffect(() => {
    if (graphNodes.length === 0) {
      apiGet<Template[]>('/templates').then((templates) => {
        if (templates.length > 0) {
          const t = templates[0];
          apiGet<Template & { graph_json: string }>(`/templates/${t.id}`).then((data) => {
            const g = JSON.parse(data.graph_json || '{}');
            if (useStore.getState().nodes.length === 0) {
              const newNodes: NodeData[] = (g.nodes || []).map((n: any) => ({
                ...n, status: 'idle' as const, paramValues: {},
              }));
              const newEdges: EdgeData[] = (g.edges || []).map((e: any) => ({
                source_node_id: e.source_node_id, source_port: e.source_port,
                target_node_id: e.target_node_id, target_port: e.target_port,
              }));
              setGraph(newNodes, newEdges);
            }
          }).catch(() => {});
        }
      }).catch(() => {});
    }
  }, []);

  const rfNodes: Node[] = graphNodes.map((n) => ({
    id: n.id,
    type: 'pipeline',
    position: { x: n.x || 0, y: n.y || 0 },
    data: {
      label: n.label,
      nodeType: n.type,
      status: n.status || 'idle',
      inputs: n.inputs,
      outputs: n.outputs,
      params: n.params,
      paramValues: n.paramValues || {},
      outputs_cache: n.outputs_cache,
      error: n.error,
    },
  }));

  const rfEdges: Edge[] = graphEdges.map((e, i) => ({
    id: `${e.source_node_id}-${e.source_port}-${e.target_node_id}-${e.target_port}-${i}`,
    source: e.source_node_id,
    target: e.target_node_id,
    sourceHandle: e.source_port,
    targetHandle: e.target_port,
    animated: running,
    style: { stroke: '#4a5568', strokeWidth: 1.5 },
  }));

  const [nodesState, , onNodesChange] = useNodesState(rfNodes);
  const [edgesState, setEdgesState, onEdgesChange] = useEdgesState(rfEdges);

  const onNodeDragStop = useCallback(
    (_: any, node: Node) => {
      const updated = graphNodes.map((n) =>
        n.id === node.id ? { ...n, x: node.position.x, y: node.position.y } : n
      );
      setGraph(updated, graphEdges);
    },
    [graphNodes, graphEdges, setGraph]
  );

  const onConnect = useCallback(
    (conn: Connection) => {
      if (!conn.source || !conn.target || !conn.sourceHandle || !conn.targetHandle) return;
      const newEdge: any = {
        source_node_id: conn.source,
        source_port: conn.sourceHandle,
        target_node_id: conn.target,
        target_port: conn.targetHandle,
      };
      setGraph(graphNodes, [...graphEdges, newEdge]);
      setEdgesState((eds) => addEdge(conn, eds));
    },
    [graphNodes, graphEdges, setGraph, setEdgesState]
  );

  const onNodeClick = useCallback(
    (_: any, node: Node) => setSelectedNodeId(node.id),
    [setSelectedNodeId]
  );

  return (
    <div className="flex-1 bg-gray-950">
      <ReactFlow
        nodes={nodesState}
        edges={edgesState}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeDragStop={onNodeDragStop}
        onConnect={onConnect}
        onNodeClick={onNodeClick}
        nodeTypes={nodeTypes}
        fitView
        deleteKeyCode={['Backspace', 'Delete']}
        className="bg-gray-950"
      >
        <Background color="#1f2937" gap={20} />
        <Controls className="!bg-gray-900 !border-gray-700 !rounded-lg" />
        <MiniMap className="!bg-gray-900 !border-gray-700 !rounded-lg" nodeColor="#374151" />
      </ReactFlow>
    </div>
  );
}
