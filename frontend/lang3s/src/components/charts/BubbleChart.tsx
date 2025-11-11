import { cn } from "@/lib/utils";
import { extent } from "d3-array";
import { drag, type D3DragEvent } from "d3-drag";
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
  showLabels?: boolean;
  onNodeClick?: (node: Point) => void;
  styles?: BubbleChartStyles;
  className?: string;
  style?: React.CSSProperties;
}

// ---------------- Component ----------------

export const BubbleChart: React.FC<BubbleSimilarityChartProps> = ({
  data,
  showLabels = true,
  onNodeClick,
  styles = {},
  className,
  style,
}) => {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const tooltipRef = useRef<HTMLDivElement | null>(null);
  const zoomBehaviorRef = useRef<ZoomBehavior<SVGSVGElement, unknown> | null>(
    null,
  );
  const [dimensions, setDimensions] = useState({ width: 400, height: 400 });

  useEffect(() => {
    if (!data?.points?.length) return;

    const {
      backgroundColor = "#fff",
      linkColor = "#999",
      linkOpacity = 0.4,
      nodeFill = "#69b3a2",
      nodeStroke = "#333",
      nodeStrokeWidth = 0.5,
      centerNodeColor = "#ff8c00",
      labelColor = "#111",
      labelFontSize = 11,
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
      .range([8, 40]);

    const centralNode = data.points.reduce((a, b) =>
      a.support > b.support ? a : b,
    );

    const nodes: Point[] = data.points.map((p) => ({
      ...p,
      r: radiusScale(p.support),
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
      .attr("stroke-width", (d: Similarity) => d.similarity * 2);

    const node = g
      .append("g")
      .selectAll<SVGCircleElement, Point>("circle")
      .data(nodes)
      .join("circle")
      .attr("r", (d: Point) => d.r ?? 10)
      .attr("fill", (d: Point) =>
        d.id === centralNode.id
          ? centerNodeColor
          : typeof nodeFill === "function"
            ? nodeFill(d)
            : nodeFill,
      )
      .attr("stroke", nodeStroke)
      .attr("stroke-width", nodeStrokeWidth)
      // .call(
      //   drag<SVGCircleElement, Point>()
      //     .on("start", (event: D3DragEvent<SVGCircleElement, Point, Point>) => {
      //       if (!event.active) simulation.alphaTarget(0.3).restart();
      //       event.subject.fx = event.subject.x;
      //       event.subject.fy = event.subject.y;
      //     })
      //     .on("drag", (event: D3DragEvent<SVGCircleElement, Point, Point>) => {
      //       event.subject.fx = event.x;
      //       event.subject.fy = event.y;
      //     })
      //     .on("end", (event: D3DragEvent<SVGCircleElement, Point, Point>) => {
      //       if (!event.active) simulation.alphaTarget(0);
      //       event.subject.fx = null;
      //       event.subject.fy = null;
      //     }),
      // )
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
        .data(nodes)
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
        .text((d) => d.name);
    }

    // --- Simulation setup ---
    const simulation: Simulation<Point, Similarity> = forceSimulation<Point>(
      nodes,
    )
      .force(
        "link",
        forceLink<Point, Similarity>(links)
          .id((d: Point) => d.id)
          .distance((d: Similarity) => 300 - d.similarity * 100),
      )
      .force("charge", forceManyBody().strength(-100))
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

      if (labels) labels.attr("x", (d) => d.x ?? 0).attr("y", (d) => d.y ?? 0);
    });

    simulation.on("end", () => {
      const xExtent = extent(nodes, (d) => d.x!) as [number, number];
      const yExtent = extent(nodes, (d) => d.y!) as [number, number];

      const graphWidth = xExtent[1] - xExtent[0];
      const graphHeight = yExtent[1] - yExtent[0];

      const scale = Math.min(
        dimensions.width / (graphWidth * 1.5),
        dimensions.height / (graphHeight * 1.5),
      );

      const translateX =
        dimensions.width / 2 - scale * (xExtent[0] + graphWidth / 2);
      const translateY =
        dimensions.height / 2 - scale * (yExtent[0] + graphHeight / 2);

      const initialTransform = zoomIdentity
        .translate(translateX, translateY)
        .scale(scale);

      svg
        .transition()
        .duration(50)
        .call(zoomBehavior.transform as any, initialTransform);
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
  }, [data, dimensions, showLabels, styles, onNodeClick]);

  useEffect(() => {
    const element = wrapperRef.current;
    if (!element) return;

    const resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry?.contentRect) {
        setDimensions({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
      }
    });

    resizeObserver.observe(element);
    return () => resizeObserver.disconnect();
  }, []);

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
        style={{
          position: "absolute",
          top: "10px",
          right: "15px",
          background: "rgba(255,255,255,0.9)",
          borderRadius: "8px",
          padding: "4px",
          boxShadow: "0 2px 4px rgba(0,0,0,0.2)",
          display: "flex",
          flexDirection: "column",
          gap: "4px",
        }}
      >
        <button onClick={handleZoomIn} className="p-2 hover:bg-slate-100">
          <ZoomInIcon className="size-4" />
        </button>
        <button onClick={handleZoomOut} className="p-2 hover:bg-slate-100">
          <ZoomOutIcon className="size-4" />
        </button>
        <button onClick={handleResetZoom} className="p-2 hover:bg-slate-100">
          <RotateCcwIcon className="size-4" />
        </button>
        <button onClick={handleRecenter} className="p-2 hover:bg-slate-100">
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
