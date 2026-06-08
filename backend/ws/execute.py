import json
import asyncio
import os
from typing import Dict, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect
from models.flow import FlowDefinition
from engine.executor import FlowExecutor, ExecutionError, InfiniteLoopError
from storage.trace_store import TraceStore


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
trace_store = TraceStore(os.path.join(BASE_DIR, "flows", "traces"))


class ExecutionConnection:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.executor: Optional[FlowExecutor] = None
        self.execution_task: Optional[asyncio.Task] = None

    async def send(self, message: Dict[str, Any]) -> None:
        await self.websocket.send_json(message)

    async def handle_message(self, data: Dict[str, Any]) -> None:
        msg_type = data.get('type')

        if msg_type == 'execute':
            await self.handle_execute(data)
        elif msg_type == 'pause':
            await self.handle_pause()
        elif msg_type == 'resume':
            await self.handle_resume()
        elif msg_type == 'step':
            await self.handle_step()
        elif msg_type == 'stop':
            await self.handle_stop()
        elif msg_type == 'setVariable':
            await self.handle_set_variable(data)
        else:
            await self.send({
                'type': 'error',
                'message': f"Unknown message type: {msg_type}"
            })

    async def handle_execute(self, data: Dict[str, Any]) -> None:
        if self.execution_task and not self.execution_task.done():
            await self.send({
                'type': 'error',
                'message': "An execution is already in progress. Stop it first."
            })
            return

        try:
            flow_data = data.get('flow')
            if not flow_data:
                await self.send({
                    'type': 'error',
                    'message': "No flow definition provided"
                })
                return

            flow = FlowDefinition(**flow_data)
            self.executor = FlowExecutor(flow)

            self.executor.set_callbacks(
                on_node_enter=self._on_node_enter,
                on_node_exit=self._on_node_exit,
                on_node_error=self._on_node_error,
                on_status_change=self._on_status_change,
                on_trace=self._on_trace,
                on_completed=self._on_completed
            )

            self.execution_task = asyncio.create_task(self._run_execution())

        except Exception as e:
            await self.send({
                'type': 'error',
                'message': f"Failed to start execution: {str(e)}"
            })

    async def _run_execution(self) -> None:
        try:
            await self.executor.execute()
        except InfiniteLoopError as e:
            await self.send({
                'type': 'error',
                'message': f"Infinite loop detected: {str(e)}"
            })
            await self.send({
                'type': 'status',
                'status': 'error',
                'variables': dict(self.executor.state.variables)
            })
        except ExecutionError as e:
            await self.send({
                'type': 'error',
                'message': f"Execution error: {str(e)}"
            })
            await self.send({
                'type': 'status',
                'status': 'error',
                'variables': dict(self.executor.state.variables)
            })
        except Exception as e:
            await self.send({
                'type': 'error',
                'message': f"Unexpected error: {str(e)}"
            })
            await self.send({
                'type': 'status',
                'status': 'error',
                'variables': dict(self.executor.state.variables) if self.executor else {}
            })

    async def handle_pause(self) -> None:
        if not self.executor:
            await self.send({
                'type': 'error',
                'message': "No execution in progress"
            })
            return
        await self.executor.pause()

    async def handle_resume(self) -> None:
        if not self.executor:
            await self.send({
                'type': 'error',
                'message': "No execution in progress"
            })
            return
        await self.executor.resume()

    async def handle_step(self) -> None:
        if not self.executor:
            await self.send({
                'type': 'error',
                'message': "No execution in progress"
            })
            return
        await self.executor.step()

    async def handle_stop(self) -> None:
        if not self.executor:
            return
        await self.executor.stop()
        if self.execution_task and not self.execution_task.done():
            try:
                await asyncio.wait_for(self.execution_task, timeout=2.0)
            except asyncio.TimeoutError:
                self.execution_task.cancel()

    async def handle_set_variable(self, data: Dict[str, Any]) -> None:
        if not self.executor:
            await self.send({
                'type': 'error',
                'message': "No execution in progress"
            })
            return
        name = data.get('name')
        value = data.get('value')
        if not name:
            await self.send({
                'type': 'error',
                'message': "Variable name is required"
            })
            return
        self.executor.set_variable(name, value)
        await self.send({
            'type': 'status',
            'status': self.executor.state.status,
            'variables': dict(self.executor.state.variables)
        })

    async def _on_node_enter(self, node_id: str, variables: Dict[str, Any]) -> None:
        await self.send({
            'type': 'nodeEnter',
            'nodeId': node_id,
            'variables': dict(variables)
        })

    async def _on_node_exit(self, node_id: str, variables: Dict[str, Any]) -> None:
        await self.send({
            'type': 'nodeExit',
            'nodeId': node_id,
            'variables': dict(variables)
        })

    async def _on_node_error(self, node_id: str, error: str, variables: Dict[str, Any]) -> None:
        await self.send({
            'type': 'nodeError',
            'nodeId': node_id,
            'error': error,
            'variables': dict(variables)
        })

    async def _on_status_change(self, status: str, variables: Dict[str, Any]) -> None:
        await self.send({
            'type': 'status',
            'status': status,
            'variables': dict(variables)
        })

    async def _on_trace(self, log: Any) -> None:
        await self.send({
            'type': 'trace',
            'log': log.model_dump()
        })

    async def _on_completed(self, variables: Dict[str, Any], trace: list) -> None:
        if self.executor and self.executor.flow:
            try:
                trace_store.save_trace(self.executor.flow.id, trace)
            except Exception:
                pass
        
        await self.send({
            'type': 'completed',
            'variables': dict(variables),
            'trace': [log.model_dump() for log in trace]
        })


async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connection = ExecutionConnection(websocket)
    
    try:
        while True:
            try:
                data = await websocket.receive_json()
                await connection.handle_message(data)
            except json.JSONDecodeError:
                await connection.send({
                    'type': 'error',
                    'message': "Invalid JSON message"
                })
            except Exception as e:
                await connection.send({
                    'type': 'error',
                    'message': f"Message handling error: {str(e)}"
                })
    except WebSocketDisconnect:
        if connection.executor:
            await connection.executor.stop()
        if connection.execution_task and not connection.execution_task.done():
            connection.execution_task.cancel()
