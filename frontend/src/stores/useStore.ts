import { create } from 'zustand';
import type { Task, Template, NodeData, EdgeData } from '../types';

interface AppState {
  // Tasks
  tasks: Task[];
  currentTaskId: string | null;
  setTasks: (tasks: Task[]) => void;
  setCurrentTaskId: (id: string | null) => void;

  // Graph in canvas
  nodes: NodeData[];
  edges: EdgeData[];
  setGraph: (nodes: NodeData[], edges: EdgeData[]) => void;
  updateNodeStatus: (nodeId: string, status: string, error?: string, outputs?: any) => void;
  updateNodeParam: (nodeId: string, paramName: string, value: any) => void;

  // Selected node
  selectedNodeId: string | null;
  setSelectedNodeId: (id: string | null) => void;

  // Templates
  templates: Template[];
  setTemplates: (templates: Template[]) => void;

  // Dialog
  templateDialogOpen: boolean;
  setTemplateDialogOpen: (open: boolean) => void;

  // Running state
  running: boolean;
  setRunning: (r: boolean) => void;
}

export const useStore = create<AppState>((set) => ({
  tasks: [],
  currentTaskId: null,
  setTasks: (tasks) => set({ tasks }),
  setCurrentTaskId: (id) => set({ currentTaskId: id }),

  nodes: [],
  edges: [],
  setGraph: (nodes, edges) => set({ nodes, edges }),
  updateNodeStatus: (nodeId, status, error, outputs) =>
    set((state) => ({
      nodes: state.nodes.map((n) =>
        n.id === nodeId ? { ...n, status: status as any, error, outputs_cache: outputs || n.outputs_cache } : n
      ),
    })),
  updateNodeParam: (nodeId, paramName, value) =>
    set((state) => ({
      nodes: state.nodes.map((n) =>
        n.id === nodeId
          ? { ...n, paramValues: { ...(n.paramValues || {}), [paramName]: value } }
          : n
      ),
    })),

  selectedNodeId: null,
  setSelectedNodeId: (id) => set({ selectedNodeId: id }),

  templates: [],
  setTemplates: (templates) => set({ templates }),

  templateDialogOpen: false,
  setTemplateDialogOpen: (open) => set({ templateDialogOpen: open }),

  running: false,
  setRunning: (r) => set({ running: r }),
}));
