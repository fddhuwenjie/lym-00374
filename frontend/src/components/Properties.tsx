import React, { useCallback } from 'react';
import CodeMirror from '@uiw/react-codemirror';
import { python } from '@codemirror/lang-python';
import { oneDark } from '@codemirror/theme-one-dark';
import { X, Settings, Type, Code, GitBranch, RotateCcw, Clock } from 'lucide-react';
import { useFlowStore } from '../store/useFlowStore';
import type { FlowNode, NodeType } from '../types/flow';

interface PropertiesProps {
  nodes: FlowNode[];
}

const nodeIcons: Record<NodeType, React.ReactNode> = {
  start: <Type size={16} />,
  end: <Type size={16} />,
  task: <Code size={16} />,
  condition: <GitBranch size={16} />,
  loop: <RotateCcw size={16} />,
  wait: <Clock size={16} />,
};

const nodeTypeTitles: Record<NodeType, string> = {
  start: 'Start Node',
  end: 'End Node',
  task: 'Task Node',
  condition: 'Condition Node',
  loop: 'Loop Node',
  wait: 'Wait Node',
};

export const Properties: React.FC<PropertiesProps> = () => {
  const { selectedNodeId, nodes, updateNodeData, setSelectedNodeId, deleteNode } = useFlowStore();

  const selectedNode = nodes.find((n) => n.id === selectedNodeId);

  const onCodeChange = useCallback(
    (value: string) => {
      if (selectedNodeId) {
        updateNodeData(selectedNodeId, { code: value });
      }
    },
    [selectedNodeId, updateNodeData]
  );

  if (!selectedNode) {
    return (
      <div className="w-80 bg-slate-800 border-l border-slate-700 p-4 overflow-y-auto">
        <h2 className="text-white font-bold text-lg mb-4 flex items-center gap-2">
          <Settings size={20} className="text-blue-400" />
          Properties
        </h2>
        <div className="text-slate-500 text-sm text-center py-8">
          Select a node to edit its properties
        </div>
      </div>
    );
  }

  const { type, data } = selectedNode;

  return (
    <div className="w-80 bg-slate-800 border-l border-slate-700 overflow-y-auto">
      <div className="p-4 border-b border-slate-700">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-white font-bold text-lg flex items-center gap-2">
            {nodeIcons[type]}
            {nodeTypeTitles[type]}
          </h2>
          <button
            onClick={() => setSelectedNodeId(null)}
            className="p-1 hover:bg-slate-700 rounded text-slate-400 hover:text-white transition-colors"
          >
            <X size={16} />
          </button>
        </div>
        <div className="text-xs text-slate-500 font-mono truncate">
          ID: {selectedNode.id}
        </div>
      </div>

      <div className="p-4 space-y-4">
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">
            Label
          </label>
          <input
            type="text"
            value={data.label}
            onChange={(e) => updateNodeData(selectedNode.id, { label: e.target.value })}
            className="w-full bg-slate-700 text-white px-3 py-2 rounded border border-slate-600 focus:outline-none focus:border-blue-500 text-sm"
          />
        </div>

        {type === 'task' && (
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Python Code
            </label>
            <div className="border border-slate-600 rounded overflow-hidden">
              <CodeMirror
                value={data.code || ''}
                height="200px"
                theme={oneDark}
                extensions={[python()]}
                onChange={onCodeChange}
                basicSetup={{
                  lineNumbers: true,
                  highlightActiveLineGutter: true,
                  highlightActiveLine: true,
                }}
              />
            </div>
            <div className="mt-2 text-xs text-slate-500">
              Access variables via <code className="bg-slate-700 px-1 rounded">ctx["name"]</code>
            </div>
          </div>
        )}

        {(type === 'condition' || type === 'loop') && (
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Expression
            </label>
            <input
              type="text"
              value={data.expression || ''}
              onChange={(e) => updateNodeData(selectedNode.id, { expression: e.target.value })}
              className="w-full bg-slate-700 text-white px-3 py-2 rounded border border-slate-600 focus:outline-none focus:border-blue-500 text-sm font-mono"
              placeholder="e.g., ctx.x > 0"
            />
            <div className="mt-2 text-xs text-slate-500">
              Use <code className="bg-slate-700 px-1 rounded">ctx.variable</code> to access context
            </div>
          </div>
        )}

        {type === 'wait' && (
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Wait Time (seconds)
            </label>
            <input
              type="number"
              min="0"
              step="0.1"
              value={data.seconds ?? 1}
              onChange={(e) => updateNodeData(selectedNode.id, { seconds: parseFloat(e.target.value) })}
              className="w-full bg-slate-700 text-white px-3 py-2 rounded border border-slate-600 focus:outline-none focus:border-blue-500 text-sm"
            />
          </div>
        )}

        {type === 'loop' && (
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Loop Anchor Node ID
            </label>
            <input
              type="text"
              value={data.anchorId || ''}
              onChange={(e) => updateNodeData(selectedNode.id, { anchorId: e.target.value })}
              className="w-full bg-slate-700 text-white px-3 py-2 rounded border border-slate-600 focus:outline-none focus:border-blue-500 text-sm font-mono"
              placeholder="Node ID to loop back to"
            />
            <div className="mt-2 text-xs text-slate-500">
              The node ID that the loop should return to when condition is true
            </div>
          </div>
        )}

        {(type !== 'start' && type !== 'end') && (
          <button
            onClick={() => {
              deleteNode(selectedNode.id);
              setSelectedNodeId(null);
            }}
            className="w-full mt-4 px-4 py-2 bg-red-500/20 text-red-400 rounded hover:bg-red-500/30 transition-colors text-sm font-medium"
          >
            Delete Node
          </button>
        )}
      </div>
    </div>
  );
};
