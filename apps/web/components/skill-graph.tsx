"use client";

import dagre from "@dagrejs/dagre";
import { useEffect, useRef, useState } from "react";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
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

gsap.registerPlugin(useGSAP);

type NodeData = {
  label: string;
  role: SkillNodeData["role"];
  status: SkillNodeData["status"];
  capabilityId: string;
  pointName: string | null;
  kind: "root" | "group" | "capability" | "point";
};

const NODE_WIDTH = 156;
const NODE_HEIGHT = 58;

function layoutGraph(nodes: Node<NodeData>[], edges: Edge[], compact: boolean) {
  const nodeWidth = compact ? 132 : NODE_WIDTH;
  const nodeHeight = compact ? 54 : NODE_HEIGHT;
  const graph = new dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
  graph.setGraph({
    rankdir: "LR",
    nodesep: compact ? 18 : 24,
    ranksep: compact ? 64 : 100,
    marginx: compact ? 18 : 28,
    marginy: compact ? 18 : 28,
  });
  nodes.forEach((node) => graph.setNode(node.id, { width: nodeWidth, height: nodeHeight }));
  edges.forEach((edge) => graph.setEdge(edge.source, edge.target));
  dagre.layout(graph);
  return nodes.map((node) => {
    const position = graph.node(node.id);
    return {
      ...node,
      position: {
        x: position.x - nodeWidth / 2,
        y: position.y - nodeHeight / 2,
      },
    };
  });
}

function SkillNode({
  data,
  selected,
}: {
  data: NodeData;
  selected: boolean;
}) {
  const classes = ["graph-node", `graph-node-${data.kind}`, `graph-node-${data.role}`];
  if (data.status !== "stable") classes.push(`graph-node-${data.status}`);
  if (selected) classes.push("graph-node-selected");
  return (
    <div
      className={classes.join(" ")}
      data-capability-id={data.capabilityId}
      data-point-name={data.pointName ?? ""}
    >
      <Handle position={Position.Left} type="target" />
      <div className="graph-node-label">{data.label}</div>
      <div className="graph-node-meta">
        <span>
          {data.kind === "root"
            ? "岗位"
            : data.kind === "group"
              ? "能力分组"
            : `${data.pointName ? "技能点" : "能力域"} · ${data.role === "required" ? "必备" : "加分"}`}
        </span>
        {data.status !== "stable" ? (
          <b>{data.status === "added" ? "新增" : data.status === "removed" ? "删除" : "修改"}</b>
        ) : null}
      </div>
      <Handle position={Position.Right} type="source" />
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
  const [compact, setCompact] = useState(false);
  const [activeRole, setActiveRole] = useState<SkillNodeData["role"] | null>(null);
  const canvasRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const media = window.matchMedia("(max-width: 720px)");
    const update = () => setCompact(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  const selectedNode = nodes.find((node) => node.id === selectedId);
  const expandedCapabilityId = selectedNode
    ? selectedNode.pointName
      ? selectedNode.capabilityId
      : selectedNode.id === "root"
        ? null
        : selectedNode.id
    : null;
  const availableCapabilities = nodes.filter(
    (node) => node.id !== "root" && node.pointName === null,
  );
  const availableRoles = new Set(availableCapabilities.map((node) => node.role));
  const compactRole =
    activeRole && availableRoles.has(activeRole)
      ? activeRole
      : availableRoles.size === 1
        ? [...availableRoles][0]
        : null;
  const displayedNodes = nodes.filter((node) => {
    if (!compact) return node.pointName === null || node.capabilityId === expandedCapabilityId;
    if (!compactRole) return node.id === "root";
    if (expandedCapabilityId) {
      return node.id === expandedCapabilityId || node.capabilityId === expandedCapabilityId;
    }
    return node.pointName === null && node.id !== "root" && node.role === compactRole;
  });
  const displayedIds = new Set(displayedNodes.map((node) => node.id));
  const displayedEdges = edges.filter(
    (edge) => displayedIds.has(edge.source) && displayedIds.has(edge.target),
  );
  const capabilityNodes = displayedNodes.filter(
    (node) => node.id !== "root" && node.pointName === null,
  );
  const groupNodes: Node<NodeData>[] = (["required", "preferred"] as const)
    .map((role) => ({
      role,
      count: availableCapabilities.filter((node) => node.role === role).length,
    }))
    .filter(
      (group) =>
        group.count > 0 && (!compact || !compactRole || group.role === compactRole),
    )
    .map((group) => ({
      id: `group-${group.role}`,
      type: "skill",
      position: { x: 0, y: 0 },
      data: {
        label: group.role === "required" ? "必备能力" : "加分能力",
        role: group.role,
        status: "stable" as const,
        capabilityId: "",
        pointName: null,
        kind: "group" as const,
      },
      selectable: false,
    }));
  const dataNodes: Node<NodeData>[] = displayedNodes.map((node): Node<NodeData> => ({
    id: node.id,
    type: "skill",
    position: { x: 0, y: 0 },
    data: {
      label: node.label,
      role: node.role,
      status: node.status,
      capabilityId: node.capabilityId,
      pointName: node.pointName,
      kind: node.id === "root" ? "root" : node.pointName ? "point" : "capability",
    },
    selected: node.id === selectedId,
  }));
  const baseNodes: Node<NodeData>[] = [...dataNodes, ...groupNodes];

  const hierarchyEdges = displayedEdges
    .filter((edge) => edge.source !== "root")
    .map((edge) => ({ id: edge.id, source: edge.source, target: edge.target }))
    .concat(
      displayedIds.has("root")
        ? groupNodes.map((group) => ({
            id: `e-root-${group.id}`,
            source: "root",
            target: group.id,
          }))
        : [],
      capabilityNodes.map((node) => ({
        id: `e-group-${node.id}`,
        source: `group-${node.role}`,
        target: node.id,
      })),
    );
  const flowEdges: Edge[] = hierarchyEdges.map((edge) => ({
    ...edge,
    type: "default",
    className:
      edge.source === selectedId || edge.target === selectedId
        ? "graph-edge graph-edge-active"
        : "graph-edge",
    pathOptions: { curvature: 0.28 },
  }));
  const flowNodes = layoutGraph(baseNodes, flowEdges, compact);
  const layoutKey = flowNodes.map((node) => node.id).join(":");

  useGSAP(
    (_, contextSafe) => {
      const media = gsap.matchMedia();
      const runAnimation = () => {
        media.add("(prefers-reduced-motion: no-preference)", () => {
          const nodeTargets = canvasRef.current?.querySelectorAll(".graph-node");
          const edgeTargets = canvasRef.current?.querySelectorAll(".react-flow__edge-path");
          if (nodeTargets?.length) {
            gsap.fromTo(
              nodeTargets,
              { autoAlpha: 0.72, scale: 0.98 },
              { autoAlpha: 1, scale: 1, duration: 0.24, ease: "power2.out", stagger: 0.018 },
            );
          }
          if (edgeTargets?.length) {
            gsap.fromTo(
              edgeTargets,
              { opacity: 0.15 },
              { opacity: 1, duration: 0.3, ease: "power1.out" },
            );
          }
        });
      };
      const animate = contextSafe ? contextSafe(runAnimation) : runAnimation;
      const frame = window.requestAnimationFrame(animate);
      return () => {
        window.cancelAnimationFrame(frame);
        media.revert();
      };
    },
    { dependencies: [layoutKey], scope: canvasRef, revertOnUpdate: true },
  );

  return (
    <div className="skill-graph-canvas" ref={canvasRef}>
      <ReactFlowProvider>
        <ReactFlow
          key={layoutKey}
          edges={flowEdges}
          fitView
          fitViewOptions={{ padding: 0.12, minZoom: 0.55, maxZoom: 1 }}
          minZoom={0.45}
          maxZoom={1.5}
          nodeTypes={nodeTypes}
          nodes={flowNodes}
          nodesConnectable={false}
          nodesDraggable={false}
          onNodeClick={(_, node) => {
            if (node.id.startsWith("group-")) {
              if (compact) {
                setActiveRole((current) =>
                  current === node.data.role ? null : node.data.role,
                );
                onSelect(null);
              }
              return;
            }
            onSelect(node.id);
          }}
          onPaneClick={() => onSelect(null)}
          proOptions={{ hideAttribution: true }}
        >
          <Background
            color="var(--line)"
            gap={28}
            size={1}
            variant={BackgroundVariant.Dots}
          />
          <Controls showInteractive={false} />
        </ReactFlow>
      </ReactFlowProvider>
    </div>
  );
}
