"use client";
import { cn } from "@/lib/utils/cn";
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  type Simulation,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from "d3-force";
import { scaleSqrt } from "d3-scale";
import { select, type Selection } from "d3-selection";
import { zoom, zoomIdentity, type ZoomBehavior } from "d3-zoom";
import {
  RotateCcwIcon,
  SquareSquareIcon,
  ZoomInIcon,
  ZoomOutIcon,
} from "lucide-react";
import React, { useEffect, useRef, useState } from "react";
import { useResizeObserver } from "@/components/charts/useResizeObserver";

// ---------------- Types ----------------

export interface Point extends SimulationNodeDatum {
  id: string;
  name: string;
  support: number;
  r?: number;
  x?: number;
  y?: number;
  fx?: number | null;
  fy?: number | null;
  color?: string;
}

export interface Similarity extends SimulationLinkDatum<Point> {
  id1: string;
  id2: string;
  similarity: number;
  source: Point;
  target: Point;
}

export interface BubbleChartStyles {
  backgroundColor?: string;
  linkColor?: string;
  linkOpacity?: number;
  nodeFill?: string | ((node: Point) => string);
  nodeStroke?: string;
  nodeStrokeWidth?: number;
  centerNodeColor?: string;
  labelColor?: string;
  labelFontSize?: number | ((node: Point) => number);
  tooltipBg?: string;
  tooltipTextColor?: string;
}

export interface BubbleSimilarityChartProps {
  data: {
    points: Point[];
    similarities: Omit<Similarity, "source" | "target">[];
  };
  splitLabels?: string;
  showLabels?: boolean;
  minSupportToShowLabel?: number;
  onNodeClick?: (node: Point) => void;
  styles?: BubbleChartStyles;
  className?: string;
  style?: React.CSSProperties;
  minNodeSize?: number;
  maxNodeSize?: number;
  linkScaleFactor?: number;
}

// ---------------- Component ----------------

export const ForceGraph: React.FC<BubbleSimilarityChartProps> = ({
  data,
  showLabels = true,
  splitLabels,
  onNodeClick,
  styles = {},
  className,
  minNodeSize = 8,
  minSupportToShowLabel = 100,
  maxNodeSize = 70,
  linkScaleFactor = 2,
  style,
}) => {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const tooltipRef = useRef<HTMLDivElement | null>(null);
  const zoomBehaviorRef = useRef<ZoomBehavior<SVGSVGElement, unknown> | null>(
    null,
  );
  const { dimensions } = useResizeObserver({
    wrapperRef,
  });

  useEffect(() => {
    if (!data?.points?.length) return;

    const {
      backgroundColor = "#fff",
      linkColor = "#999",
      linkOpacity = 0.4,
      nodeFill = (n) => "#69b3a2",
      nodeStroke = "#333",
      nodeStrokeWidth = 0.5,
      centerNodeColor = "#ff8c00",
      labelColor = "#fff",
      labelFontSize = 6,
      tooltipBg = "rgba(0,0,0,0.8)",
      tooltipTextColor = "#fff",
    } = styles;

    const svg = select(svgRef.current);
    svg.selectAll("*").remove(); // Clear previous content
    svg
      .attr("width", dimensions.width - 20)
      .attr("height", dimensions.height - 20)
      .style("background-color", backgroundColor);

    const tooltip = select(tooltipRef.current)
      .style("position", "absolute")
      .style("visibility", "hidden")
      .style("background", tooltipBg)
      .style("color", tooltipTextColor)
      .style("padding", "6px 10px")
      .style("border-radius", "6px")
      .style("font-size", "12px")
      .style("transition", "opacity 0.2s ease")
      .style("opacity", "0")
      .style("pointer-events", "none");

    // --- Setup scales ---
    const supports = data.points.map((p) => p.support);
    const radiusScale = scaleSqrt()
      .domain([Math.min(...supports), Math.max(...supports)])
      .range([minNodeSize, maxNodeSize]);

    const centralNode = data.points.reduce((a, b) =>
      a.support > b.support ? a : b,
    );

    const nodes: Point[] = data.points.map((p) => ({
      ...p,
      r: p.r ? p.r : radiusScale(p.support),
      x: dimensions.width / 2 + Math.random() * 10,
      y: dimensions.height / 2 + Math.random() * 10,
    }));

    const nodeMap = new Map<string, Point>(nodes.map((n) => [n.id, n]));

    const links: Similarity[] = data.similarities
      .map((s) => {
        const source = nodeMap.get(s.id1);
        const target = nodeMap.get(s.id2);
        if (!source || !target) return null;
        return { ...s, source, target } as Similarity;
      })
      .filter((l): l is Similarity => l !== null);

    // --- Create SVG groups ---
    const g = svg.append("g");

    const link = g
      .append("g")
      .attr("stroke", linkColor)
      .attr("stroke-opacity", linkOpacity)
      .selectAll<SVGLineElement, Similarity>("line")
      .data(links)
      .join("line")
      .attr("stroke-width", (d: Similarity) => d.similarity * linkScaleFactor);

    const node = g
      .append("g")
      .selectAll<SVGCircleElement, Point>("circle")
      .data(nodes)
      .join("circle")
      .attr("r", (d: Point) => d.r ?? 10)
      .attr("fill", (d: Point) =>
        d.color
          ? d.color
          : d.id === centralNode.id
            ? centerNodeColor
            : typeof nodeFill === "function"
              ? nodeFill(d)
              : nodeFill,
      )
      .attr("stroke", nodeStroke)
      .style("cursor", onNodeClick ? "pointer" : "default")
      .attr("stroke-width", nodeStrokeWidth)
      .on("mouseover", (event: any, d: Point) => {
        tooltip.style("visibility", "visible").text(`${d.name} (${d.support})`);
      })
      .on("mousemove", (event: { pageY: number; pageX: number }) => {
        const bounds = (
          wrapperRef.current as HTMLDivElement
        ).getBoundingClientRect();
        tooltip
          .style("opacity", 1)
          .style("left", `${event.pageX - bounds.left + 10}px`)
          .style("top", `${event.pageY - bounds.top + 10}px`);
      })
      .on("mouseout", () =>
        tooltip.style("opacity", 0).style("visibility", "hidden"),
      )
      .on("click", (_: any, d: Point) => onNodeClick?.(d));

    let labels: Selection<SVGTextElement, Point, SVGGElement, unknown> | null =
      null;
    if (showLabels) {
      labels = g
        .append("g")
        .selectAll<SVGTextElement, Point>("text")
        .data(nodes.filter((n) => n.support > minSupportToShowLabel))
        .join("text")
        .attr("text-anchor", "middle")
        .attr("dy", 4)
        .attr("fill", labelColor)
        .style("pointer-events", "none")
        .style("font-size", (d: Point) =>
          typeof labelFontSize === "function"
            ? `${labelFontSize(d)}px`
            : `${labelFontSize}px`,
        )
        .each(function (d) {
          // 1. Clear existing content (crucial for re-renders/updates)
          this.textContent = "";

          const lines = (
            splitLabels ? d.name.split(splitLabels) : [d.name]
          ).slice(0, 4);
          lines[lines.length - 1] = lines[lines.length - 1] + "...";
          const lineHeight = 1.2; // em
          const ns = "http://www.w3.org/2000/svg"; // Required for creating SVG elements

          lines.forEach((line, i) => {
            const tspan = document.createElementNS(ns, "tspan");

            tspan.textContent = line;
            tspan.setAttribute("x", "0"); // Keep centered

            let dyValue;
            if (i === 0) {
              dyValue = `${0.35 - ((lines.length - 1) * lineHeight) / 2}em`;
            } else {
              dyValue = `${lineHeight}em`;
            }

            tspan.setAttribute("dy", dyValue);
            this.appendChild(tspan);
          });
        });
    }

    // --- Simulation setup ---
    const simulation: Simulation<Point, Similarity> = forceSimulation<Point>(
      nodes,
    )
      .force(
        "link",
        forceLink<Point, Similarity>(links)
          .id((d: Point) => d.id)
          .distance((d: Similarity) => (1 - d.similarity) * 100),
      )
      .force("charge", forceManyBody().strength(-20))
      .force("center", forceCenter(dimensions.width / 2, dimensions.height / 2))
      .force(
        "collide",
        forceCollide<Point>().radius((d) => (d.r ?? 10) + 4),
      );

    simulation.on("tick", () => {
      link
        .attr("x1", (d) => d.source.x ?? 0)
        .attr("y1", (d) => d.source.y ?? 0)
        .attr("x2", (d) => d.target.x ?? 0)
        .attr("y2", (d) => d.target.y ?? 0);

      node.attr("cx", (d) => d.x ?? 0).attr("cy", (d) => d.y ?? 0);

      if (labels) labels.attr("transform", (d) => `translate(${d.x},${d.y})`);
    });

    simulation.on("end", () => {
      const { width, height } = dimensions;
      svg
        .transition()
        .duration(500)
        .call(
          zoomBehaviorRef.current!.translateTo as any,
          width / 2,
          height / 2,
        );

      zoomBehaviorRef.current?.scaleBy(
        svg.transition().duration(500) as any,
        0.5,
      );
    });

    // --- Zoom & Pan ---
    const zoomBehavior: ZoomBehavior<SVGSVGElement, unknown> = zoom<
      SVGSVGElement,
      unknown
    >().on("zoom", (event: { transform: any }) =>
      g.attr("transform", event.transform),
    );

    svg.call(zoomBehavior as any);
    zoomBehaviorRef.current = zoomBehavior;
    // Cleanup on unmount
    return () => {
      simulation.stop();
      svg.selectAll("*").remove();
    };
  }, [
    data,
    dimensions,
    showLabels,
    splitLabels,
    styles,
    onNodeClick,
    minNodeSize,
    maxNodeSize,
    minSupportToShowLabel,
    linkScaleFactor,
  ]);

  // --- Zoom controls
  const handleZoomIn = () => {
    const svg = select(svgRef.current);
    const t = svg.transition().duration(250);
    zoomBehaviorRef.current?.scaleBy(t as any, 1.2);
  };

  const handleZoomOut = () => {
    const svg = select(svgRef.current);
    zoomBehaviorRef.current?.scaleBy(
      svg.transition().duration(250) as any,
      0.8,
    );
  };

  const handleResetZoom = () => {
    const svg = select(svgRef.current);
    svg
      .transition()
      .duration(500)
      .call(zoomBehaviorRef.current?.transform as any, zoomIdentity);
  };

  const handleRecenter = () => {
    const svg = select(svgRef.current);
    const { width, height } = dimensions;
    svg
      .transition()
      .duration(500)
      .call(zoomBehaviorRef.current!.translateTo as any, width / 2, height / 2);
  };

  return (
    <div
      ref={wrapperRef}
      className="relative h-full min-h-0 w-full flex-1 grow"
    >
      <div
        className="bg-white/90 dark:bg-zinc-800/90"
        style={{
          position: "absolute",
          top: "10px",
          right: "15px",
          borderRadius: "8px",
          padding: "4px",
          boxShadow: "0 2px 4px rgba(0,0,0,0.2)",
          display: "flex",
          flexDirection: "column",
          gap: "4px",
        }}
      >
        <button
          onClick={handleZoomIn}
          className="p-2 hover:bg-slate-100 dark:hover:bg-zinc-700"
        >
          <ZoomInIcon className="size-4" />
        </button>
        <button
          onClick={handleZoomOut}
          className="p-2 hover:bg-slate-100 dark:hover:bg-zinc-700"
        >
          <ZoomOutIcon className="size-4" />
        </button>
        <button
          onClick={handleResetZoom}
          className="p-2 hover:bg-slate-100 dark:hover:bg-zinc-700"
        >
          <RotateCcwIcon className="size-4" />
        </button>
        <button
          onClick={handleRecenter}
          className="p-2 hover:bg-slate-100 dark:hover:bg-zinc-700"
        >
          <SquareSquareIcon className="size-4" />
        </button>
      </div>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${dimensions.width} ${dimensions.height}`}
        className={cn(
          "m-auto h-full w-full opacity-0 transition-opacity duration-300 ease-in",
          dimensions && "opacity-100",
          className,
        )}
        style={style}
        preserveAspectRatio="xMidYMid meet"
      />
      <div ref={tooltipRef} />
    </div>
  );
};
