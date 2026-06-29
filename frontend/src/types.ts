export interface PortSpec {
  name: string; port_type: string; required: boolean; description: string;
}

export interface ParamSpec {
  name: string; param_type: string; default: any; description: string; options?: any[];
}

export interface NodeData {
  id: string; type: string; label: string; x: number; y: number;
  status: 'idle' | 'queued' | 'running' | 'done' | 'failed' | 'skipped';
  inputs: Record<string, PortSpec>;
  outputs: Record<string, PortSpec>;
  params: Record<string, ParamSpec>;
  paramValues?: Record<string, any>;
  outputs_cache?: Record<string, any>;
  error?: string;
}

export interface EdgeData {
  source_node_id: string; source_port: string;
  target_node_id: string; target_port: string;
}

export interface GraphData {
  template_id?: string; metadata?: Record<string, any>;
  nodes: NodeData[]; edges: EdgeData[];
}

export interface Task {
  id: string; name: string; status: string; current_step: string;
  graph_json: string; result_json: string; error: string;
  created_at: string; updated_at: string;
}

export interface Template {
  id: string; name: string; description?: string; builtin: boolean; graph_json?: string;
}

export type WsEvent = {
  type: string; node_id: string | null;
  data: { status?: string; progress?: number; outputs?: any; error?: string; task_id?: string; success?: boolean };
};
