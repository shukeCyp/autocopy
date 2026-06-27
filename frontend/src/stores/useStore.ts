import { create } from 'zustand';
import type { Task, Template, NodeData, EdgeData } from '../types';
import type { Language } from '../i18n';

type Theme = 'dark' | 'light';

interface AppState {
  // Tasks
  tasks: Task[];
  currentTaskId: string | null;
  setTasks: (tasks: Task[]) => void;
  setCurrentTaskId: (id: string | null) => void;

  // Graph in canvas
  nodes: NodeData[];
  edges: EdgeData[];
  graphVersion: number;
  setGraph: (nodes: NodeData[], edges: EdgeData[]) => void;
  replaceGraph: (nodes: NodeData[], edges: EdgeData[], templateId?: string | null, builtin?: boolean, name?: string) => void;
  updateNodeStatus: (nodeId: string, status: string, error?: string, outputs?: any) => void;
  updateNodeParam: (nodeId: string, paramName: string, value: any) => void;

  // Selected node
  selectedNodeId: string | null;
  setSelectedNodeId: (id: string | null) => void;

  // Templates
  templates: Template[];
  activeTemplateId: string | null;
  workflowName: string;
  setTemplates: (templates: Template[]) => void;
  setActiveTemplateId: (id: string | null) => void;
  setWorkflowName: (name: string) => void;
  activeTemplateBuiltin: boolean;
  setActiveTemplateBuiltin: (builtin: boolean) => void;

  // Dialog
  templateDialogOpen: boolean;
  setTemplateDialogOpen: (open: boolean) => void;

  // Running state
  running: boolean;
  setRunning: (r: boolean) => void;

  // UI
  language: Language;
  setLanguage: (language: Language) => void;
  theme: Theme;
  setTheme: (theme: Theme) => void;
}

export const useStore = create<AppState>((set) => ({
  tasks: [],
  currentTaskId: null,
  setTasks: (tasks) => set({ tasks }),
  setCurrentTaskId: (id) => set({ currentTaskId: id }),

  nodes: [],
  edges: [],
  graphVersion: 0,
  setGraph: (nodes, edges) => set({ nodes, edges }),
  replaceGraph: (nodes, edges, templateId = null, builtin = false, name = '') =>
    set((state) => ({
      nodes,
      edges,
      activeTemplateId: templateId,
      workflowName: name,
      activeTemplateBuiltin: Boolean(templateId && builtin),
      selectedNodeId: null,
      graphVersion: state.graphVersion + 1,
    })),
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
  activeTemplateId: null,
  workflowName: '',
  activeTemplateBuiltin: false,
  setTemplates: (templates) => set({ templates }),
  setActiveTemplateId: (id) => set({ activeTemplateId: id }),
  setWorkflowName: (name) => set({ workflowName: name }),
  setActiveTemplateBuiltin: (builtin) => set({ activeTemplateBuiltin: builtin }),

  templateDialogOpen: false,
  setTemplateDialogOpen: (open) => set({ templateDialogOpen: open }),

  running: false,
  setRunning: (r) => set({ running: r }),

  language: 'zh',
  setLanguage: (language) => set({ language }),
  theme: 'dark',
  setTheme: (theme) => set({ theme }),
}));
