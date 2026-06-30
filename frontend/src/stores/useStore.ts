import { create } from 'zustand';
import type { Task, Template, NodeData, EdgeData, ValidationIssue } from '../types';
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
  replaceGraph: (nodes: NodeData[], edges: EdgeData[], templateId?: string | null, name?: string) => void;
  updateNodeStatus: (nodeId: string | null, status: string, error?: string, outputs?: any, validationIssues?: ValidationIssue[]) => void;
  setNodeValidationIssues: (nodeId: string | null, issues: ValidationIssue[]) => void;
  appendNodeLog: (nodeId: string, level: string, message: string) => void;
  applyNodeResults: (results: any[]) => void;
  updateNodeParam: (nodeId: string, paramName: string, value: any) => void;

  // Selected node
  selectedNodeId: string | null;
  setSelectedNodeId: (id: string | null) => void;
  executingNodeId: string | null;
  setExecutingNodeId: (id: string | null) => void;

  // Templates
  templates: Template[];
  activeTemplateId: string | null;
  workflowName: string;
  setTemplates: (templates: Template[]) => void;
  setActiveTemplateId: (id: string | null) => void;
  setWorkflowName: (name: string) => void;

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
  replaceGraph: (nodes, edges, templateId = null, name = '') =>
    set((state) => ({
      nodes,
      edges,
      activeTemplateId: templateId,
      workflowName: name,
      selectedNodeId: null,
      executingNodeId: null,
      graphVersion: state.graphVersion + 1,
    })),
  updateNodeStatus: (nodeId, status, error, outputs, validationIssues) =>
    set((state) => ({
      nodes: state.nodes.map((n) =>
        n.id === nodeId
          ? {
              ...n,
              status: status as any,
              error,
              outputs_cache: outputs || (status === 'running' ? undefined : n.outputs_cache),
              logs: status === 'running' ? [] : n.logs,
              validationIssues: validationIssues !== undefined
                ? validationIssues
                : status === 'running' || status === 'done'
                  ? []
                  : n.validationIssues,
            }
          : n
      ),
    })),
  setNodeValidationIssues: (nodeId, issues) =>
    set((state) => ({
      nodes: state.nodes.map((n) =>
        n.id === nodeId
          ? { ...n, validationIssues: issues }
          : n
      ),
    })),
  appendNodeLog: (nodeId, level, message) =>
    set((state) => ({
      nodes: state.nodes.map((n) =>
        n.id === nodeId
          ? {
              ...n,
              logs: [
                ...(n.logs || []),
                { level, message, created_at: new Date().toISOString() },
              ],
            }
          : n
      ),
    })),
  applyNodeResults: (results) =>
    set((state) => {
      const byId = new Map(results.map((result) => [result.node_id, result]));
      return {
        nodes: state.nodes.map((n) => {
          const result = byId.get(n.id);
          if (!result) return n;
          const nextLogs = n.logs && n.logs.length > 0
            ? n.logs
            : result.error
              ? [{ level: 'error', message: result.error }]
              : n.logs;
          return {
            ...n,
            status: result.status || n.status,
            error: result.error || undefined,
            outputs_cache: result.outputs && Object.keys(result.outputs).length > 0 ? result.outputs : n.outputs_cache,
            logs: nextLogs,
            validationIssues: result.validation_issues || n.validationIssues,
          };
        }),
      };
    }),
  updateNodeParam: (nodeId, paramName, value) =>
    set((state) => ({
      nodes: state.nodes.map((n) =>
        n.id === nodeId
          ? {
              ...n,
              paramValues: { ...(n.paramValues || {}), [paramName]: value },
              validationIssues: [],
            }
          : n
      ),
    })),

  selectedNodeId: null,
  setSelectedNodeId: (id) => set({ selectedNodeId: id }),
  executingNodeId: null,
  setExecutingNodeId: (id) => set({ executingNodeId: id }),

  templates: [],
  activeTemplateId: null,
  workflowName: '',
  setTemplates: (templates) => set({ templates }),
  setActiveTemplateId: (id) => set({ activeTemplateId: id }),
  setWorkflowName: (name) => set({ workflowName: name }),

  templateDialogOpen: false,
  setTemplateDialogOpen: (open) => set({ templateDialogOpen: open }),

  running: false,
  setRunning: (r) => set({ running: r }),

  language: 'zh',
  setLanguage: (language) => set({ language }),
  theme: 'dark',
  setTheme: (theme) => set({ theme }),
}));
