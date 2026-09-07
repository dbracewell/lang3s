import {
  ForceGraphMouseEvent,
  ForceGraphPoint,
  ForceGraphSimilarity,
  simulationFn,
} from "@/components/d3/ForceGraph/types";
import { cn } from "@/lib/utils/cn";
import { select } from "d3-selection";
import { forceSimulation, Simulation } from "d3-force";
import { zoom, ZoomBehavior } from "d3-zoom";
import React, { ReactNode, useEffect, useRef } from "react";
import { defaultSimulator } from "@/components/d3/ForceGraph/functions";
import { OnInitializeFn, SVGStyleFn } from "@/components/d3/types";
import { useD3Context } from "@/components/d3/D3ContextType";

type ForceGraphProps<Point extends ForceGraphPoint> = {
  points: Point[];
  similarities: Omit<ForceGraphSimilarity<Point>, "source" | "target">[];
  svgClassName?: string;
  wrapperClassName?: string;
  fontScaler?: (point: Point) => number;
  nodeScaler?: (point: Point) => number;
  colliderFn?: (point: Point) => number;
  onMouseEnter?: ForceGraphMouseEvent<Point>;
  onMouseOut?: ForceGraphMouseEvent<Point>;
  onMouseClick?: ForceGraphMouseEvent<Point>;
  linkClassName?: string;
  textClassName?: string;
  nodeClassName?: string;
  styleFn?: SVGStyleFn;
  textSplitlines?: boolean;
  simulator?: simulationFn<Point>;
  onInitialize?: OnInitializeFn;
  children?: ReactNode;
};

const ForceGraphBase = <Point extends ForceGraphPoint>({
  points,
  similarities,
  svgClassName,
  wrapperClassName,
  fontScaler,
  nodeScaler,
  onMouseEnter,
  onMouseOut,
  onMouseClick,
  linkClassName,
  textClassName,
  textSplitlines = true,
  styleFn,
  nodeClassName,
  simulator,
  colliderFn,
  onInitialize,
  children,
}: ForceGraphProps<Point>) => {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const zoomBehaviorRef = useRef<ZoomBehavior<SVGSVGElement, unknown> | null>(
    null,
  );
  const { registerRef, getRef, setHoveredNode } = useD3Context<Point>();

  useEffect(() => {
    const wrapperRef = getRef("wrapper");

    if (!svgRef.current || !wrapperRef?.current || !points.length) {
      return;
    }

    const bounds = wrapperRef.current.getBoundingClientRect();
    const { width, height } = bounds;

    const svg = select(svgRef.current);
    svg.selectAll("*").remove();

    svg
      .attr("viewBox", `0 0 ${width} ${height}`)
      .attr("width", width)
      .attr("height", height);

    const nodes: Point[] = points.map((p) => ({
      ...p,
      r: p.r ?? 20,
      x: width / 2 + Math.random() * 10,
      y: height / 2 + Math.random() * 10,
    }));

    const nodeMap = new Map<string, Point>(nodes.map((n) => [n.id, n]));

    const links: ForceGraphSimilarity<Point>[] = similarities
      .map((s) => {
        const source = nodeMap.get(s.id1);
        const target = nodeMap.get(s.id2);
        return source && target
          ? ({ ...s, source, target } as ForceGraphSimilarity<Point>)
          : null;
      })
      .filter((l): l is ForceGraphSimilarity<Point> => l !== null);

    const g = svg.append("g");

    onInitialize?.({ g, getRef });

    g.append("g")
      .selectAll("line")
      .data(links)
      .join("line")
      .attr("class", linkClassName ?? "");

    g.append("g")
      .selectAll("circle")
      .data(nodes)
      .join("circle")
      .attr("class", cn("fill-current", nodeClassName))
      .attr("r", (d) => (nodeScaler ? nodeScaler(d) : (d.r ?? 10)))
      .on("mouseenter", (event: MouseEvent, point: Point) => {
        let handleHover =
          onMouseEnter?.({
            event,
            point,
            nodes,
            links,
            getRef,
            setHoveredNode,
          }) ?? true;
        if (handleHover) {
          setHoveredNode(point);
        }
      })
      .on("mouseout", (event: MouseEvent, point: Point) => {
        const close =
          onMouseOut?.({
            event,
            point,
            nodes,
            links,
            getRef,
            setHoveredNode,
          }) ?? true;
        if (close) {
          setHoveredNode(null);
        }
      })
      .on("click", (event: MouseEvent, point: Point) => {
        onMouseClick?.({ event, point, nodes, links, getRef, setHoveredNode });
      });

    const labels = g
      .append("g")
      .selectAll<SVGTextElement, Point>("text")
      .data(nodes)
      .join("text")
      .attr("class", cn("node-label", textClassName))
      .attr("text-anchor", "middle")
      .text((d) => d.display)
      .style("font-size", (d) => (fontScaler ? fontScaler(d) : "16px"));

    if (textSplitlines) {
      labels.each(function (d) {
        const lines: string[] = [];
        this.textContent = "";
        const splits = d.display.split(" ");
        for (let i = 0; i < splits.length; i++) {
          let c = splits[i];
          while (
            c.length < 15 &&
            i + 1 < splits.length &&
            `${c} ${splits[i + 1]}`.length < 15
          ) {
            i++;
            c = `${c} ${splits[i]}`;
          }
          lines.push(c);
        }
        const lineHeight = 1.2;
        const ns = "http://www.w3.org/2000/svg";
        lines.forEach((line, i) => {
          const tspan = document.createElementNS(ns, "tspan");
          tspan.textContent = line;
          tspan.setAttribute("x", "0");
          tspan.setAttribute(
            "dy",
            i === 0
              ? `${0.35 - ((lines.length - 1) * lineHeight) / 2}em`
              : `${lineHeight}em`,
          );
          this.appendChild(tspan);
        });
      });
    }

    const simulation: Simulation<
      Point,
      ForceGraphSimilarity<Point>
    > = forceSimulation<Point>(nodes);

    const zoomBehavior: ZoomBehavior<SVGSVGElement, unknown> = zoom<
      SVGSVGElement,
      unknown
    >().on("zoom", (event) => {
      g.attr("transform", event.transform);
      const tooltip = getRef("tooltip").current;
      if (tooltip !== null) {
        tooltip.style.visibility = "hidden";
      }
    });

    svg.call(zoomBehavior as any);
    zoomBehaviorRef.current = zoomBehavior;
    registerRef("zoomBehavior", zoomBehaviorRef);

    const finalSimulator = simulator != null ? simulator : defaultSimulator;

    finalSimulator({
      simulation,
      nodes,
      links,
      width,
      height,
      colliderFn,
      svg: svgRef.current,
      getRef,
      setHoveredNode,
    });

    return () => {
      simulation.stop();
      svg.selectAll("*").remove();
    };
  }, [
    points,
    similarities,
    fontScaler,
    nodeScaler,
    colliderFn,
    getRef,
    onMouseEnter,
    onMouseOut,
    onMouseClick,
    textClassName,
    textSplitlines,
    nodeClassName,
    linkClassName,
    simulator,
    setHoveredNode,
  ]);

  useEffect(() => {
    if (svgRef.current == null || styleFn == null) return;
    styleFn(svgRef.current);
  }, [styleFn, points]);

  return (
    <div
      ref={(node) => {
        wrapperRef.current = node;
        registerRef("wrapper", wrapperRef);
      }}
      className={cn(
        "relative flex h-full min-h-0 w-full flex-1 flex-col",
        wrapperClassName,
      )}
    >
      {children}
      <svg
        ref={(node) => {
          svgRef.current = node;
          registerRef("svg", svgRef);
        }}
        className={cn("h-full w-full select-none", svgClassName)}
        preserveAspectRatio="xMidYMid meet"
      />
    </div>
  );
};

export const ForceGraph = React.memo(ForceGraphBase) as typeof ForceGraphBase;
