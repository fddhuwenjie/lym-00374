from typing import Literal, Optional, Dict, Any, List
from pydantic import BaseModel, Field

NodeType = Literal['start', 'end', 'task', 'condition', 'loop', 'wait']
ExecutionStatus = Literal['idle', 'running', 'paused', 'stopped', 'completed', 'error']
TraceAction = Literal['enter', 'exit', 'error']
EdgeHandle = Literal['true', 'false', 'loop']


class Position(BaseModel):
    x: float
    y: float


class NodeData(BaseModel):
    label: str
    code: Optional[str] = None
    expression: Optional[str] = None
    seconds: Optional[float] = None
    anchorId: Optional[str] = None


class FlowNode(BaseModel):
    id: str
    type: NodeType
    position: Position
    data: NodeData


class FlowEdge(BaseModel):
    id: str
    source: str
    target: str
    sourceHandle: Optional[EdgeHandle] = None


class FlowDefinition(BaseModel):
    id: str
    name: str
    nodes: List[FlowNode]
    edges: List[FlowEdge]
    createdAt: float
    updatedAt: float


class TraceLog(BaseModel):
    timestamp: float
    nodeId: str
    nodeType: NodeType
    action: TraceAction
    variables: Dict[str, Any] = Field(default_factory=dict)
    message: Optional[str] = None


class ExecutionState(BaseModel):
    flowId: str
    status: ExecutionStatus
    currentNodeId: Optional[str] = None
    variables: Dict[str, Any] = Field(default_factory=dict)
    trace: List[TraceLog] = Field(default_factory=list)
    loopCounts: Dict[str, int] = Field(default_factory=dict)
