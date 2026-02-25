"use client";
import React, { useMemo, useState } from "react";
import * as d3 from "d3";
import { cn } from "@/lib/utils/cn";
import {
  Command,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { useChart } from "@/components/charts/useChart";
import {
  RotateCcwIcon,
  SquareSquareIcon,
  ZoomInIcon,
  ZoomOutIcon,
} from "lucide-react";

interface Node {
  id: string;
  group: string; // The category (e.g., "Marketing", "Sales")
}

interface Link {
  source: string;
  target: string;
  value: number;
}

interface CircularBundlingProps {
  data: {
    nodes: Node[];
    links: Link[];
  };
  width?: number;
  height?: number;
}

interface HierarchyDatum {
  name: string;
  children?: HierarchyDatum[];
  group?: string;
  id?: string;
}

const CircularEdgeBundling: React.FC<CircularBundlingProps> = ({ data }) => {
  const { wrapperRef, svgRef, contentRef, dimensions } = useChart();
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);

  // 1. Transform Flat Data into Hierarchy (Root -> Category -> Concept)
  const hierarchyData = useMemo(() => {
    const root: HierarchyDatum = { name: "root", children: [] as any[] };
    const groups = new Map<string, HierarchyDatum>();

    // Create groups
    data.nodes.forEach((n) => {
      if (!groups.has(n.group)) {
        const groupNode = { name: n.group, children: [] };
        groups.set(n.group, groupNode);
        root.children!.push(groupNode);
      }
      groups.get(n.group)!.children!.push({ name: n.id, ...n });
    });

    return root;
  }, [data]);

  const { nodes, paths, neighbors, fontSize } = useMemo(() => {
    if (!dimensions.width || !dimensions.height)
      return {
        nodes: [] as d3.HierarchyNode<HierarchyDatum>[],
        paths: [],
        neighbors: new Map<string, Set<string>>(),
        fontSize: 10,
      };

    // Maximizing radius to create space
    const radius = Math.min(dimensions.width, dimensions.height) / 1.5 - 50;
    // Leave 120px padding for text labels
    const innerRadius = radius - 220;

    const cluster = d3.cluster<HierarchyDatum>().size([360, innerRadius]);
    const root = d3.hierarchy<HierarchyDatum>(hierarchyData);

    cluster(root);

    const leafNodes = root.leaves();
    const map = new Map(leafNodes.map((d) => [d.data.name, d]));

    const processedPaths = data.links
      .map((link) => {
        const source = map.get(link.source);
        const target = map.get(link.target);
        if (!source || !target) return null;
        return {
          ...link,
          path: source.path(target),
          sourceNode: source,
          targetNode: target,
        };
      })
      .filter(Boolean) as any[];

    // Build neighbor map for fast lookups during hover
    const neighborMap = new Map<string, Set<string>>();
    data.links.forEach((l) => {
      if (!neighborMap.has(l.source)) neighborMap.set(l.source, new Set());
      if (!neighborMap.has(l.target)) neighborMap.set(l.target, new Set());
      neighborMap.get(l.source)!.add(l.target);
      neighborMap.get(l.target)!.add(l.source);
    });

    // Determine font size based on node count to prevent overlapping
    // If > 100 nodes, shrink text. If > 200, shrink more.
    const fontSize = leafNodes.length > 50 ? 6 : 12;

    return {
      nodes: leafNodes,
      paths: processedPaths,
      neighbors: neighborMap,
      fontSize,
    };
  }, [hierarchyData, data.links, dimensions]);

  // 3. Helper to determine active connections
  const activeNeighbors = useMemo(() => {
    return hoveredNode
      ? neighbors.get(hoveredNode) || new Set<string>()
      : new Set<string>();
  }, [hoveredNode, neighbors]);

  // 3. Line Generator (Radial + Bundle Curve)
  const line = d3
    .lineRadial<any>()
    .curve(d3.curveBundle.beta(0.85)) // 0.85 = tight bundling
    .radius((d: any) => d.y)
    .angle((d: any) => (d.x / 180) * Math.PI);

  const color = d3.scaleOrdinal(d3.schemeCategory10);

  return (
    <div
      ref={wrapperRef}
      className="relative flex flex-1 justify-center overflow-hidden p-4"
    >
      <div
        className="absolute top-4 right-4 flex min-h-0 flex-col gap-2 overflow-hidden"
        style={{
          height: dimensions.height,
        }}
      >
        <Command className="bg-card/50 w-62 border shadow-xl">
          <CommandInput />
          <CommandList className="max-h-full!">
            <CommandEmpty>Nothing found</CommandEmpty>
            {nodes.map((v, i) => (
              <CommandItem
                key={v.data.name}
                className={cn(
                  "hover:text-foreground bg-row/50 cursor-pointer truncate rounded-none px-3 py-1 hover:font-bold hover:underline",
                  i % 2 == 1 && "bg-alternate-row/50",
                )}
                onMouseEnter={() => setHoveredNode(v.data.name)}
                onMouseLeave={() => setHoveredNode(null)}
              >
                {v.data.name}
              </CommandItem>
            ))}
          </CommandList>
        </Command>
      </div>
      <svg
        ref={svgRef}
        width={dimensions.width}
        height={dimensions.height}
        viewBox={`${-dimensions.width / 2} ${-dimensions.height / 2} ${dimensions.width} ${dimensions.height}`}
        className="cursor-move active:cursor-grabbing"
      >
        {/* LINKS (Bundled Paths) */}
        <g ref={contentRef}>
          <g>
            {paths.map((d, i) => {
              const isConnected = hoveredNode
                ? d.source === hoveredNode || d.target === hoveredNode
                : false;

              const isDimmed = hoveredNode && !isConnected;

              return (
                <path
                  key={i}
                  d={line(d.path) || ""}
                  fill="none"
                  stroke={
                    isConnected
                      ? color(d.sourceNode.parent.data.name)
                      : "#cbd5e1"
                  }
                  strokeOpacity={isDimmed ? 0.05 : 0.4}
                  strokeWidth={isConnected ? 2 : 1}
                  className="transition-all duration-300 ease-in-out"
                />
              );
            })}
          </g>

          {/* NODES (Text Labels) */}
          <g>
            {nodes.map((node: any, i) => {
              const angle = node.x;
              const radius = node.y;
              const name = node.data.name;

              const isHovered = hoveredNode === node.data.name;
              const isNeighbor = activeNeighbors.has(name);
              const isDimmed =
                hoveredNode && hoveredNode !== node.data.name && !isNeighbor;

              return (
                <g
                  key={i}
                  transform={`rotate(${angle - 90}) translate(${radius},0)`}
                >
                  <text
                    dy="0.31em"
                    x={angle < 180 ? 8 : -8}
                    textAnchor={angle < 180 ? "start" : "end"}
                    transform={angle >= 180 ? "rotate(180)" : undefined}
                    className={`cursor-pointer transition-all duration-200 select-none ${isHovered ? "z-50 font-bold" : ""}`}
                    style={{
                      opacity: isDimmed ? 0.1 : 1,
                      fill:
                        isHovered || isNeighbor
                          ? "var(--color-foreground)"
                          : color(node.parent.data.name),
                      fontSize: isHovered
                        ? `${fontSize + 4}px`
                        : isNeighbor
                          ? `${fontSize + 2}px`
                          : `${fontSize}px`,
                      textShadow: isHovered
                        ? "0 0 10px rgba(0,0,0,0.8)"
                        : "none",
                    }}
                    onMouseEnter={() => setHoveredNode(name)}
                    onMouseLeave={() => setHoveredNode(null)}
                  >
                    {name}
                  </text>
                </g>
              );
            })}
          </g>
        </g>
      </svg>

      <div className="pointer-events-none absolute top-4 left-4 flex flex-col gap-2">
        {hoveredNode ? (
          <div className="bg-card/50 min-w-70 rounded-lg border pb-3 text-sm shadow-xl backdrop-blur">
            <div className="bg-heading mb-1 text-center text-lg font-bold">
              {hoveredNode}
            </div>
            <div className="text-muted-foreground mb-1 text-center text-sm">
              Correlated Concepts
            </div>
            <div className="font-mono text-xs text-blue-400">
              {[...activeNeighbors].map((v) => (
                <div key={v} className="px-3">
                  {v}
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="bg-card/50 rounded p-2 text-xs text-gray-500 italic">
            Scroll to Zoom • Drag to Pan • Hover to Focus
          </div>
        )}
      </div>
    </div>
  );
};

export default CircularEdgeBundling;
