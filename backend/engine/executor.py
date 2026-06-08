import asyncio
import time
from typing import Dict, Any, List, Optional, Callable, Coroutine
from models.flow import (
    FlowDefinition, FlowNode, FlowEdge,
    TraceLog, ExecutionState, ExecutionStatus
)
from engine.ast_eval import evaluate_expression, ASTEvaluationError
from engine.sandbox import execute_python_sandbox, SandboxError
from engine.validator import FlowValidator, ValidationError


MAX_LOOP_COUNT = 10000


class ExecutionError(Exception):
    pass


class InfiniteLoopError(ExecutionError):
    pass


class FlowExecutor:
    def __init__(self, flow: FlowDefinition):
        self.flow = flow
        self.nodes: Dict[str, FlowNode] = {n.id: n for n in flow.nodes}
        self.edges: List[FlowEdge] = flow.edges

        self.outgoing: Dict[str, List[FlowEdge]] = {}
        self.incoming: Dict[str, List[FlowEdge]] = {}

        for edge in self.edges:
            if edge.source not in self.outgoing:
                self.outgoing[edge.source] = []
            self.outgoing[edge.source].append(edge)

            if edge.target not in self.incoming:
                self.incoming[edge.target] = []
            self.incoming[edge.target].append(edge)

        self.state = ExecutionState(
            flowId=flow.id,
            status='idle'
        )

        self._should_stop = False
        self._should_pause = False
        self._step_mode = False
        self._step_event = asyncio.Event()
        self._pause_event = asyncio.Event()
        self._pause_event.set()

        self._on_node_enter: Optional[Callable[[str, Dict[str, Any]], Coroutine]] = None
        self._on_node_exit: Optional[Callable[[str, Dict[str, Any]], Coroutine]] = None
        self._on_node_error: Optional[Callable[[str, str, Dict[str, Any]], Coroutine]] = None
        self._on_status_change: Optional[Callable[[ExecutionStatus, Dict[str, Any]], Coroutine]] = None
        self._on_trace: Optional[Callable[[TraceLog], Coroutine]] = None
        self._on_completed: Optional[Callable[[Dict[str, Any], List[TraceLog]], Coroutine]] = None

    def set_callbacks(self,
                     on_node_enter=None,
                     on_node_exit=None,
                     on_node_error=None,
                     on_status_change=None,
                     on_trace=None,
                     on_completed=None):
        self._on_node_enter = on_node_enter
        self._on_node_error = on_node_error
        self._on_status_change = on_status_change
        self._on_trace = on_trace
        self._on_completed = on_completed

    def validate(self) -> None:
        validator = FlowValidator(self.flow)
        validator.validate()

    async def pause(self) -> None:
        if self.state.status == 'running':
            self._should_pause = True
            self._pause_event.clear()
            await self._set_status('paused')

    async def resume(self) -> None:
        if self.state.status == 'paused':
            self._should_pause = False
            self._pause_event.set()
            await self._set_status('running')

    async def step(self) -> None:
        if self.state.status in ['paused', 'idle']:
            self._step_mode = True
            self._step_event.set()
            if self.state.status == 'paused':
                self._should_pause = False
                self._pause_event.set()
            await self._set_status('running')

    async def stop(self) -> None:
        self._should_stop = True
        self._should_pause = False
        self._step_mode = False
        self._step_event.set()
        self._pause_event.set()
        await self._set_status('stopped')

    def set_variable(self, name: str, value: Any) -> None:
        self.state.variables[name] = value

    async def _set_status(self, status: ExecutionStatus) -> None:
        self.state.status = status
        if self._on_status_change:
            await self._on_status_change(status, dict(self.state.variables))

    async def _add_trace(self, node_id: str, node_type: str, action: str, variables: Dict[str, Any], message: Optional[str] = None) -> None:
        log = TraceLog(
            timestamp=time.time(),
            nodeId=node_id,
            nodeType=node_type,
            action=action,
            variables=dict(variables),
            message=message
        )
        self.state.trace.append(log)
        if self._on_trace:
            await self._on_trace(log)

    def _get_start_node(self) -> FlowNode:
        for node in self.flow.nodes:
            if node.type == 'start':
                return node
        raise ExecutionError("No Start node found")

    def _get_next_node(self, current_node: FlowNode, result: Optional[bool] = None, handle: Optional[str] = None) -> Optional[FlowNode]:
        outgoing = self.outgoing.get(current_node.id, [])

        if current_node.type == 'condition':
            handle_str = 'true' if result else 'false'
            for edge in outgoing:
                if edge.sourceHandle == handle_str:
                    return self.nodes[edge.target]
            raise ExecutionError(f"No {handle_str} branch found for condition node {current_node.id}")

        elif current_node.type == 'loop':
            if handle == 'loop':
                for edge in outgoing:
                    if edge.sourceHandle == 'loop':
                        return self.nodes[edge.target]
            else:
                for edge in outgoing:
                    if edge.sourceHandle is None or edge.sourceHandle != 'loop':
                        return self.nodes[edge.target]
            raise ExecutionError(f"No appropriate edge found for loop node {current_node.id}")

        else:
            if len(outgoing) == 1:
                return self.nodes[outgoing[0].target]
            raise ExecutionError(f"Expected exactly 1 outgoing edge for {current_node.id}")

    async def _execute_start_node(self, node: FlowNode) -> None:
        pass

    async def _execute_end_node(self, node: FlowNode) -> None:
        pass

    async def _execute_task_node(self, node: FlowNode) -> None:
        code = node.data.code
        if not code:
            return

        loop = asyncio.get_event_loop()
        try:
            ctx = {'ctx': self.state.variables}
            await loop.run_in_executor(
                None,
                execute_python_sandbox,
                code,
                self.state.variables,
                5
            )
        except SandboxError as e:
            raise ExecutionError(f"Task execution failed: {e}")

    async def _execute_condition_node(self, node: FlowNode) -> bool:
        expression = node.data.expression
        if not expression:
            raise ExecutionError("Condition expression is empty")

        try:
            ctx = {'ctx': self.state.variables}
            result = evaluate_expression(expression, ctx)
            return bool(result)
        except ASTEvaluationError as e:
            raise ExecutionError(f"Condition evaluation failed: {e}")

    async def _execute_loop_node(self, node: FlowNode) -> bool:
        loop_count = self.state.loopCounts.get(node.id, 0)

        if loop_count >= MAX_LOOP_COUNT:
            raise InfiniteLoopError(
                f"Infinite loop detected: Loop node '{node.id}' "
                f"exceeded maximum {MAX_LOOP_COUNT} iterations"
            )

        expression = node.data.expression
        if not expression:
            raise ExecutionError("Loop expression is empty")

        try:
            ctx = {'ctx': self.state.variables}
            result = evaluate_expression(expression, ctx)
            return bool(result)
        except ASTEvaluationError as e:
            raise ExecutionError(f"Loop condition evaluation failed: {e}")

    async def _execute_wait_node(self, node: FlowNode) -> None:
        seconds = node.data.seconds or 0
        if seconds > 0:
            await asyncio.sleep(seconds)

    async def _check_pause(self) -> None:
        if self._should_pause:
            await self._set_status('paused')
            await self._pause_event.wait()
            if not self._should_stop:
                await self._set_status('running')
            self._should_pause = False

        if self._step_mode:
            self._step_event.clear()
            await self._set_status('paused')
            await self._step_event.wait()
            if not self._should_stop and self._step_mode:
                await self._set_status('running')
                self._step_mode = False

    async def execute(self) -> ExecutionState:
        try:
            self.validate()
        except ValidationError as e:
            await self._set_status('error')
            raise ExecutionError(f"Flow validation failed: {e}")

        await self._set_status('running')
        current_node = self._get_start_node()

        try:
            while current_node.type != 'end' and not self._should_stop:

                await self._check_pause()
                if self._should_stop:
                    break

                self.state.currentNodeId = current_node.id

                await self._add_trace(
                    current_node.id,
                    current_node.type,
                    'enter',
                    self.state.variables
                )

                if self._on_node_enter:
                    await self._on_node_enter(current_node.id, dict(self.state.variables))

                await self._check_pause()
                if self._should_stop:
                    break

                try:
                    if current_node.type == 'start':
                        await self._execute_start_node(current_node)
                    elif current_node.type == 'task':
                        await self._execute_task_node(current_node)
                    elif current_node.type == 'condition':
                        pass
                    elif current_node.type == 'loop':
                        pass
                    elif current_node.type == 'wait':
                        await self._execute_wait_node(current_node)

                except ExecutionError as e:
                    await self._add_trace(
                        current_node.id,
                        current_node.type,
                        'error',
                        self.state.variables,
                        str(e)
                    )
                    if self._on_node_error:
                        await self._on_node_error(current_node.id, str(e), dict(self.state.variables))
                    await self._set_status('error')
                    raise

                await self._add_trace(
                    current_node.id,
                    current_node.type,
                    'exit',
                    self.state.variables
                )

                if self._on_node_exit:
                    await self._on_node_exit(current_node.id, dict(self.state.variables))

                await self._check_pause()
                if self._should_stop:
                    break

                if current_node.type == 'condition':
                    result = await self._execute_condition_node(current_node)
                    current_node = self._get_next_node(current_node, result=result)

                elif current_node.type == 'loop':
                    result = await self._execute_loop_node(current_node)
                    if result:
                        self.state.loopCounts[current_node.id] = self.state.loopCounts.get(current_node.id, 0) + 1
                        current_node = self._get_next_node(current_node, handle='loop')
                    else:
                        current_node = self._get_next_node(current_node, handle='exit')

                elif current_node.type == 'start':
                    current_node = self._get_next_node(current_node)

                else:
                    current_node = self._get_next_node(current_node)

            if current_node.type == 'end' and not self._should_stop:
                self.state.currentNodeId = current_node.id
                await self._add_trace(
                    current_node.id,
                    current_node.type,
                    'enter',
                    self.state.variables
                )
                if self._on_node_enter:
                    await self._on_node_enter(current_node.id, dict(self.state.variables))
                await self._execute_end_node(current_node)
                await self._add_trace(
                    current_node.id,
                    current_node.type,
                    'exit',
                    self.state.variables
                )
                if self._on_node_exit:
                    await self._on_node_exit(current_node.id, dict(self.state.variables))

            if self._should_stop:
                await self._set_status('stopped')
            else:
                await self._set_status('completed')

            if self._on_completed:
                await self._on_completed(dict(self.state.variables), list(self.state.trace))

        except ExecutionError as e:
            await self._set_status('error')
            raise

        return self.state

    def get_state(self) -> ExecutionState:
        return self.state
