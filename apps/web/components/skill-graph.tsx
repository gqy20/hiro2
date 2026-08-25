"use client";

import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  Position,
  ReactFlow,
  ReactFlowProvider,
  type Node,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import type { SkillNode as SkillNodeData } from "@/lib/skill";

type NodeData = {
  label: string;
  role: SkillNodeData["role"];
  status: SkillNodeData["status"];
  capabilityId: string;
  pointName: string | null;
};

function SkillNode({
  data,
  selected,
}: {
  data: NodeData;
  selected: boolean;
}) {
  const classes = ["graph-node", `graph-node-${data.role}`];
  if (data.status !== "stable") classes.push(`graph-node-${data.status}`);
  if (selected) classes.push("graph-node-selected");
  return (
    <div
      className={classes.join(" ")}
      data-capability-id={data.capabilityId}
      data-point-name={data.pointName ?? ""}
    >
      <Handle position={Position.Top} type="target" />
      <div className="graph-node-label">{data.label}</div>
      <div className="graph-node-meta">
        {data.role === "required" ? "必备" : "加分"}
        {data.pointName ? "" : ` · ${data.capabilityId}`}
      </div>
      <Handle position={Position.Bottom} type="source" />
    </div>
  );
}

const nodeTypes = { skill: SkillNode };

export function SkillGraph({
  nodes,
  edges,
  onSelect,
  selectedId,
}: {
  nodes: SkillNodeData[];
  edges: import("@/lib/skill").SkillEdge[];
  onSelect: (id: string | null) => void;
  selectedId: string | null;
}) {
  const flowNodes: Node<NodeData>[] = nodes.map((node) => ({
    id: node.id,
    type: "skill",
    position: node.position,
    data: {
      label: node.label,
      role: node.role,
      status: node.status,
      capabilityId: node.capabilityId,
      pointName: node.pointName,
    },
    selected: node.id === selectedId,
  }));

  const flowEdges: Edge[] = edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    type: "smoothstep",
    className: "graph-edge",
  }));

  return (
    <div className="skill-graph-canvas">
      <ReactFlowProvider>
        <ReactFlow
          edges={flowEdges}
          fitView
          minZoom={0.3}
          maxZoom={2}
          nodeTypes={nodeTypes}
          nodes={flowNodes}
          onNodeClick={(_, node) => onSelect(node.id)}
          onPaneClick={() => onSelect(null)}
          proOptions={{ hideAttribution: true }}
        >
          <Background
            color="var(--line)"
            gap={24}
            size={1}
            variant={BackgroundVariant.Dots}
          />
          <Controls showInteractive={false} />
        </ReactFlow>
      </ReactFlowProvider>
    </div>
  );
}