import React, { useCallback, useRef, useEffect } from 'react';
import { Toolbar } from './components/Toolbar';
import { Sidebar } from './components/Sidebar';
import { FlowEditor } from './components/FlowEditor';
import { Properties } from './components/Properties';
import { Monitor } from './components/Monitor';
import { useFlowStore, createNewNode } from './store/useFlowStore';
import { useWebSocket } from './hooks/useWebSocket';
import type { NodeType, ServerMessage, ClientMessage, FlowDefinition } from './types/flow';

const WS_URL = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/execute`;
const API_URL = '/api';

function App() {
  const {
    nodes,
    edges,
    flowName,
    flowId,
    executionState,
    wsConnected,
    errorMessage,
    setFlowName,
    setWsConnected,
    setErrorMessage,
    setActiveNodeId,
    updateExecutionStatus,
    updateVariables,
    addTraceLog,
    resetExecution,
    getFlowDefinition,
    loadFlowDefinition,
    clearFlow,
    addNode,
  } = useFlowStore();

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleMessage = useCallback(
    (message: ServerMessage) => {
      console.log('Received message:', message.type);

      switch (message.type) {
        case 'nodeEnter':
          setActiveNodeId(message.nodeId);
          updateVariables(message.variables);
          break;
        case 'nodeExit':
          updateVariables(message.variables);
          break;
        case 'nodeError':
          setActiveNodeId(message.nodeId);
          updateVariables(message.variables);
          setErrorMessage(`Node error: ${message.error}`);
          break;
        case 'status':
          updateExecutionStatus(message.status, message.variables);
          if (message.status === 'idle' || message.status === 'stopped' || message.status === 'completed' || message.status === 'error') {
            setTimeout(() => setActiveNodeId(null), 500);
          }
          break;
        case 'trace':
          addTraceLog(message.log);
          break;
        case 'completed':
          updateVariables(message.variables);
          updateExecutionStatus('completed', message.variables);
          setTimeout(() => setActiveNodeId(null), 500);
          break;
        case 'error':
          setErrorMessage(message.message);
          updateExecutionStatus('error');
          break;
      }
    },
    [setActiveNodeId, updateVariables, updateExecutionStatus, addTraceLog, setErrorMessage]
  );

  const { send, connect } = useWebSocket({
    url: WS_URL,
    onMessage: handleMessage,
    onOpen: () => setWsConnected(true),
    onClose: () => setWsConnected(false),
    onError: () => setWsConnected(false),
  });

  const sendMessage = useCallback(
    (message: ClientMessage) => {
      send(message);
    },
    [send]
  );

  const onDragStart = useCallback(
    (event: React.DragEvent, nodeType: NodeType) => {
      event.dataTransfer.setData('application/reactflow', nodeType);
      event.dataTransfer.effectAllowed = 'move';
    },
    []
  );

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();

      const type = event.dataTransfer.getData('application/reactflow') as NodeType;
      if (!type) return;

      const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
      const x = event.clientX - rect.left - 70;
      const y = event.clientY - rect.top - 30;

      const newNode = createNewNode(type, { x, y });
      addNode(newNode);
    },
    [addNode]
  );

  const handleRun = useCallback(() => {
    if (executionState.status !== 'idle') {
      resetExecution();
    }
    const flow = getFlowDefinition();
    sendMessage({ type: 'execute', flow });
  }, [executionState.status, getFlowDefinition, sendMessage, resetExecution]);

  const handlePause = useCallback(() => {
    sendMessage({ type: 'pause' });
  }, [sendMessage]);

  const handleResume = useCallback(() => {
    sendMessage({ type: 'resume' });
  }, [sendMessage]);

  const handleStep = useCallback(() => {
    sendMessage({ type: 'step' });
  }, [sendMessage]);

  const handleStop = useCallback(() => {
    sendMessage({ type: 'stop' });
  }, [sendMessage]);

  const handleSave = useCallback(async () => {
    try {
      const flow = getFlowDefinition();
      const response = await fetch(`${API_URL}/flows/${flow.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(flow),
      });

      if (!response.ok) {
        await fetch(`${API_URL}/flows`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(flow),
        });
      }
      alert('Flow saved successfully!');
    } catch (error) {
      alert('Failed to save flow: ' + (error as Error).message);
    }
  }, [getFlowDefinition]);

  const handleLoad = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleFileLoad = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (!file) return;

      try {
        const text = await file.text();
        const flow = JSON.parse(text) as FlowDefinition;
        loadFlowDefinition(flow);
        alert('Flow loaded successfully!');
      } catch (error) {
        alert('Failed to load flow: ' + (error as Error).message);
      }
      event.target.value = '';
    },
    [loadFlowDefinition]
  );

  const handleExport = useCallback(() => {
    const flow = getFlowDefinition();
    const data = JSON.stringify(flow, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${flow.name || 'flow'}_${flow.id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [getFlowDefinition]);

  const handleClear = useCallback(() => {
    if (confirm('Clear all nodes and edges?')) {
      clearFlow();
      resetExecution();
    }
  }, [clearFlow, resetExecution]);

  useEffect(() => {
    if (executionState.status === 'idle' && nodes.length === 0) {
      const startNode = createNewNode('start', { x: 100, y: 200 });
      const endNode = createNewNode('end', { x: 400, y: 200 });
      addNode(startNode);
      addNode(endNode);
    }
  }, []);

  useEffect(() => {
    connect();
  }, [connect]);

  return (
    <div className="h-screen flex flex-col bg-slate-900 text-white overflow-hidden">
      <Toolbar
        onRun={handleRun}
        onPause={handlePause}
        onResume={handleResume}
        onStep={handleStep}
        onStop={handleStop}
        onSave={handleSave}
        onLoad={handleLoad}
        onExport={handleExport}
        onClear={handleClear}
        status={executionState.status}
        wsConnected={wsConnected}
        flowName={flowName}
        onFlowNameChange={setFlowName}
      />

      {errorMessage && (
        <div className="bg-red-500/20 border-b border-red-500 px-4 py-2 text-red-400 text-sm flex items-center justify-between">
          <span>{errorMessage}</span>
          <button
            onClick={() => setErrorMessage(null)}
            className="text-red-300 hover:text-white"
          >
            ✕
          </button>
        </div>
      )}

      <div className="flex-1 flex overflow-hidden">
        <Sidebar onDragStart={onDragStart} />

        <div className="flex-1 flex flex-col overflow-hidden">
          <FlowEditor
            onDragStart={onDragStart}
            onDragOver={onDragOver}
            onDrop={onDrop}
          />
        </div>

        <Properties nodes={nodes} />
      </div>

      <Monitor />

      <input
        type="file"
        ref={fileInputRef}
        accept=".json"
        onChange={handleFileLoad}
        className="hidden"
      />
    </div>
  );
}

export default App;
