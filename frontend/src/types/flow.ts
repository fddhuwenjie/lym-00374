export type NodeType = 'start' | 'end' | 'task' | 'condition' | 'loop' | 'wait';
export type ExecutionStatus = 'idle' | 'running' | 'paused' | 'stopped' | 'completed' | 'error';
export type TraceAction = 'enter' | 'exit' | 'error';
export type EdgeHandle = 'true' | 'false' | 'loop';

export interface Position {
  x: number;
  y: number;
}

export interface NodeData {
  label: string;
  code?: string;
  expression?: string;
  seconds?: number;
  anchorId?: string;
}

export interface FlowNode {
  id: string;
  type: NodeType;
  position: Position;
  data: NodeData;
}

export interface FlowEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: EdgeHandle;
}

export interface FlowDefinition {
  id: string;
  name: string;
  nodes: FlowNode[];
  edges: FlowEdge[];
  createdAt: number;
  updatedAt: number;
}

export interface TraceLog {
  timestamp: number;
  nodeId: string;
  nodeType: NodeType;
  action: TraceAction;
  variables: Record<string, any>;
  message?: string;
}

export interface ExecutionState {
  flowId: string;
  status: ExecutionStatus;
  currentNodeId: string | null;
  variables: Record<string, any>;
  trace: TraceLog[];
  loopCounts: Record<string, number>;
}

export type ClientMessage =
  | { type: 'execute'; flow: FlowDefinition }
  | { type: 'pause' }
  | { type: 'resume' }
  | { type: 'step' }
  | { type: 'stop' }
  | { type: 'setVariable'; name: string; value: any };

export type ServerMessage =
  | { type: 'nodeEnter'; nodeId: string; variables: Record<string, any> }
  | { type: 'nodeExit'; nodeId: string; variables: Record<string, any> }
  | { type: 'nodeError'; nodeId: string; error: string; variables: Record<string, any> }
  | { type: 'status'; status: ExecutionStatus; variables: Record<string, any> }
  | { type: 'trace'; log: TraceLog }
  | { type: 'completed'; variables: Record<string, any>; trace: TraceLog[] }
  | { type: 'error'; message: string };
