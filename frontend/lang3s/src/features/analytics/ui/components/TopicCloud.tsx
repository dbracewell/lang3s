"use client";
import { cn } from "@/lib/utils/cn";
import {
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
  type Simulation,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from "d3-force";
import { select } from "d3-selection";
import { zoom, type ZoomBehavior, zoomIdentity } from "d3-zoom";
import {
  BinocularsIcon,
  ChartNoAxesGanttIcon,
  FileIcon,
  MessageSquareIcon,
  RotateCcwIcon,
  SearchIcon,
  SquareSquareIcon,
  ZoomInIcon,
  ZoomOutIcon,
} from "lucide-react";
import React, { useEffect, useMemo, useRef, useState } from "react";
import * as d3 from "d3";
import { useTheme } from "next-themes";
import { buttonVariants } from "@/components/ui/button";
import Link from "next/link";
import { useCorpusMapParams } from "@/features/analytics/hooks/useCorpusMapParams";
import { capitalize, formatURL } from "@/lib/utils/formatters";
import { Hint } from "@/components/hint";
import { useResizeObserver } from "@/components/charts/useResizeObserver";

// ---------------- Types ----------------

export interface TopicCloudPoint extends SimulationNodeDatum {
  id: string;
  text: string;
  value: number;
  subvalues: Record<string, number>;
  r?: number;
  original?: string;
  type: "topic" | "concept" | "entity";
}

export interface Similarity extends SimulationLinkDatum<TopicCloudPoint> {
  id1: string;
  id2: string;
  similarity: number;
  source: TopicCloudPoint;
  target: TopicCloudPoint;
}

const truncateText = (text: string, maxLength = 35) => {
  if (text.length <= maxLength) return text;
  const truncated = text.substring(0, text.lastIndexOf(" ", maxLength));
  return `${truncated || text.substring(0, maxLength)}...`;
};

export interface TopicCloudProps {
  data: {
    points: TopicCloudPoint[];
    similarities: Omit<Similarity, "source" | "target">[];
  };
  onWordClick: (word: TopicCloudPoint) => void;
}

// ---------------- Component ----------------

export const TopicCloud: React.FC<TopicCloudProps> = ({
  data,
  onWordClick,
}) => {
  const { theme } = useTheme();
  const [searchParams] = useCorpusMapParams();
  const svgRef = useRef<SVGSVGElement | null>(null);
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const actionRef = useRef<HTMLDivElement | null>(null);
  const hideTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const zoomBehaviorRef = useRef<ZoomBehavior<SVGSVGElement, unknown> | null>(
    null,
  );
  const [hoveredNode, setHoveredNode] = useState<TopicCloudPoint | null>(null);
  const searchTermRef = useRef<string>(searchParams.search);
  const searchTerm = searchParams.search ?? "";
  const { dimensions } = useResizeObserver({ wrapperRef });

  useEffect(() => {
    searchTermRef.current = searchTerm;
  }, [searchTerm]);

  const valueRanges = useMemo(() => {
    if (data == null) return null;
    return data.points.reduce(
      (agg, d) => {
        if (d.value > agg[d.type]["max"]) {
          agg[d.type]["max"] = d.value;
        }
        if (d.value < agg[d.type]["min"]) {
          agg[d.type]["min"] = d.value;
        }
        return agg;
      },
      {
        topic: { min: 100000, max: 0 },
        concept: { min: 100000, max: 0 },
        entity: { min: 100000, max: 0 },
      },
    );
  }, [data]);

  const fontScales = useMemo(() => {
    if (!valueRanges) return null;
    return {
      topic: d3.scaleLinear(
        [valueRanges.topic.min, valueRanges.topic.max],
        [24, 100],
      ),
      concept: d3.scaleLinear(
        [valueRanges.concept.min, valueRanges.concept.max],
        [24, 100],
      ),
      entity: d3.scaleLinear(
        [valueRanges.entity.min, valueRanges.entity.max],
        [24, 100],
      ),
    };
  }, [valueRanges]);

  const colorScales = useMemo(() => {
    if (!valueRanges) return null;
    return {
      topic: d3
        .scaleSequential((t) => d3.interpolateBlues(0.2 + t * 0.7))
        .domain([
          theme === "dark" ? valueRanges.topic.max : valueRanges.topic.min,
          theme === "dark" ? valueRanges.topic.min : valueRanges.topic.max,
        ]),
      concept: d3
        .scaleSequential((t) => d3.interpolateGreens(0.2 + t * 0.6))
        .domain([
          theme === "dark" ? valueRanges.concept.max : valueRanges.concept.min,
          theme === "dark" ? valueRanges.concept.min : valueRanges.concept.max,
        ]),
      entity: d3
        .scaleSequential((t) => d3.interpolatePurples(0.4 + t * 0.6))
        .domain([
          theme === "dark" ? valueRanges.entity.max : valueRanges.entity.min,
          theme === "dark" ? valueRanges.entity.min : valueRanges.entity.max,
        ]),
    };
  }, [valueRanges, theme]);

  useEffect(() => {
    if (!data?.points?.length || !fontScales) return;

    const bounds = (
      wrapperRef.current as HTMLDivElement
    ).getBoundingClientRect();
    const width = bounds.width; //wrapperRef.current?.clientWidth ?? 800;
    const height = bounds.height; //wrapperRef.current?.clientHeight ?? 800;

    const svg = select(svgRef.current);
    svg.selectAll("*").remove(); // Only clear DOM when data or dimensions change

    svg
      .attr("width", width - 20)
      .attr("height", height - 20)
      .style("background-color", "transparent");

    const actionDiv = select(actionRef.current)
      .style("position", "absolute")
      .style("visibility", "hidden")
      .style("padding", "6px 10px")
      .style("border-radius", "6px")
      .style("transition", "opacity 0.2s ease")
      .style("opacity", "0");

    // NEW: Define a helper function to handle the actual hiding logic
    const hideActionMenu = () => {
      actionDiv.style("opacity", 0).style("visibility", "hidden");
      const svg = d3.select(svgRef.current);
      setHoveredNode(null);

      if (!!searchTermRef.current) return;

      svg
        .selectAll<SVGTextElement, TopicCloudPoint>(".node-label")
        .style("opacity", 1)
        .style("filter", "none");
    };

    // NEW: Allow the popup to keep itself alive when the mouse enters it
    actionDiv
      .on("mouseenter", () => {
        if (hideTimeoutRef.current) clearTimeout(hideTimeoutRef.current);
      })
      .on("mouseleave", () => {
        if (!!searchTermRef.current) return;
        hideActionMenu();
      });

    // Initialize Nodes & Links
    const nodes: TopicCloudPoint[] = data.points.map((p) => ({
      ...p,
      r: 20,
      original: p.text,
      text: truncateText(p.text),
      x: width / 2 + Math.random() * 10,
      y: height / 2 + Math.random() * 10,
    }));

    const nodeMap = new Map<string, TopicCloudPoint>(
      nodes.map((n) => [n.id, n]),
    );
    const links: Similarity[] = data.similarities
      .map((s) => {
        const source = nodeMap.get(s.id1);
        const target = nodeMap.get(s.id2);
        return source && target
          ? ({ ...s, source, target } as Similarity)
          : null;
      })
      .filter((l): l is Similarity => l !== null);

    const g = svg.append("g");
    const hullGroup = g.append("g");

    const conceptHullPath = hullGroup
      .append("path")
      .attr("class", "concept-path")
      .style("fill", "rgba(0, 0, 0, 0.2)")
      .style("stroke-width", 0)
      .style("stroke-linejoin", "round")
      .style("pointer-events", "none");

    const link = g
      .append("g")
      .attr("stroke", "1")
      .attr("stroke-opacity", "0")
      .selectAll<SVGLineElement, Similarity>("line")
      .data(links)
      .join("line")
      .attr("stroke-width", (d) => d.similarity);

    const node = g
      .append("g")
      .selectAll<SVGCircleElement, TopicCloudPoint>("circle")
      .data(nodes)
      .join("circle")
      .attr("r", (d) => fontScales[d.type](d.value) * 1.5)
      .attr("fill", "transparent")
      .style("cursor", "pointer")
      .on("mouseenter", (event: MouseEvent, hoveredNode: TopicCloudPoint) => {
        const svg = d3.select(svgRef.current);
        if (hideTimeoutRef.current) clearTimeout(hideTimeoutRef.current);

        const bounds = (
          wrapperRef.current as HTMLDivElement
        ).getBoundingClientRect();

        const term = searchTermRef.current.trim().toLowerCase();
        const targetText = hoveredNode.original ?? hoveredNode.text;
        const isSelected = !term || targetText.toLowerCase().includes(term);
        if (!isSelected) {
          return;
        }
        // if (actionRef.current!.style.visibility === "visible") return;
        setHoveredNode(hoveredNode);
        const cursorX = event.clientX - bounds.left;
        const cursorY = event.clientY - bounds.top;

        let left = cursorX + 20;
        let top = cursorY + 20;

        actionDiv
          .style("visibility", "visible")
          .style("opacity", 1)
          .style("left", `${left}px`)
          .style("top", `${top}px`);

        if (!!searchTermRef.current) return;

        svg
          .selectAll(".node-label")
          .style("opacity", 0.2)
          .style("filter", "grayscale(50%)");

        const toHighlight = new Set(
          data.similarities
            .filter(
              (sim) =>
                (sim.id1 === hoveredNode.id || sim.id2 === hoveredNode.id) &&
                sim.similarity > 0.4,
            )
            .flatMap((sim) => [sim.id1, sim.id2]),
        );

        svg
          .selectAll<SVGTextElement, TopicCloudPoint>(".node-label")
          .filter((d) => toHighlight.has(d.id) || d.id === hoveredNode.id)
          .style("opacity", 1)
          .style("filter", "none");
      })
      .on("mouseout", () => {
        if (!!searchTermRef.current) return;
        hideTimeoutRef.current = setTimeout(() => {
          hideActionMenu();
        }, 300);
        const svg = d3.select(svgRef.current);
        svg
          .selectAll<SVGTextElement, TopicCloudPoint>(".node-label")
          .style("opacity", 1)
          .attr("stroke-opacity", "0")
          .style("filter", "none");
      })
      .on("click", (_: any, d: TopicCloudPoint) => onWordClick(d));

    // Append text nodes with the class "node-label" for our styling effect to find later
    let labels = g
      .append("g")
      .selectAll<SVGTextElement, TopicCloudPoint>(".node-label")
      .data(nodes)
      .join("text")
      .attr("class", "node-label text-select-none")
      .attr("text-anchor", "middle")
      .attr("dy", 4)
      .attr("pointer-events", "none")
      .attr("stroke-width", 2)
      .attr("stroke-opacity", "0")
      .style("font-size", (d) => fontScales[d.type](d.value))
      .each(function (d) {
        this.textContent = "";
        const splits = d.text.split(" ");
        const lines: string[] = [];
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

    // Physics Engine
    const foci = {
      topic: { x: width / 2, y: height / 3 },
      concept: { x: width / 3, y: (height * 2) / 3 },
      entity: { x: (width * 2) / 3, y: (height * 2) / 3 },
    };

    const simulation: Simulation<TopicCloudPoint, Similarity> =
      forceSimulation<TopicCloudPoint>(nodes)
        .force(
          "x",
          forceX<TopicCloudPoint>((d) => foci[d.type].x).strength(0.08),
        )
        .force(
          "y",
          forceY<TopicCloudPoint>((d) => foci[d.type].y).strength(0.08),
        )
        .force(
          "link",
          forceLink<TopicCloudPoint, Similarity>(links)
            .id((d) => d.id)
            .distance((d) => Math.max(10, (1 - d.similarity) * 100))
            .strength(0.25),
        )
        .force("charge", forceManyBody().strength(-40))
        .force(
          "collide",
          forceCollide<TopicCloudPoint>()
            .radius((d) => {
              if (d.type === "topic") return fontScales.topic(d.value) * 4;
              if (d.type === "concept")
                return fontScales.concept(d.value) * 2.5;
              return fontScales.entity(d.value) * 6;
            })
            .iterations(1),
        );

    const hullLine = d3.line().curve(d3.curveCatmullRomClosed);

    simulation
      .on("tick", () => {
        link
          .attr("x1", (d) => d.source.x ?? 0)
          .attr("y1", (d) => d.source.y ?? 0)
          .attr("x2", (d) => d.target.x ?? 0)
          .attr("y2", (d) => d.target.y ?? 0);
        node.attr("cx", (d) => d.x ?? 0).attr("cy", (d) => d.y ?? 0);
        if (labels) labels.attr("transform", (d) => `translate(${d.x},${d.y})`);

        const conceptNodes = nodes.filter(
          (d) => d.type === "concept" && d.x !== undefined && d.y !== undefined,
        );

        if (conceptNodes.length >= 3) {
          const points: [number, number][] = conceptNodes.map((d) => [
            d.x! + 20,
            d.y! + 20,
          ]);
          const hull = d3.polygonHull(points);
          if (hull) conceptHullPath.attr("d", hullLine(hull));
        } else {
          conceptHullPath.attr("d", null);
        }
      })
      .on("end", () => {
        if (searchTermRef.current == null) return;
        const searchTerm = searchTermRef.current.toLowerCase().trim();

        let toFocus: TopicCloudPoint | undefined;
        let toFocusValue = 0;
        nodes.forEach((node) => {
          if (
            !!searchTerm &&
            (node.original ?? node.text).toLowerCase() === searchTerm
          ) {
            toFocus = node;
            toFocusValue = 10000000;
          }
          if (
            node.type === "concept" &&
            (toFocus == null ||
              toFocus.type === "topic" ||
              node.value > toFocusValue)
          ) {
            toFocusValue = node.value;
            toFocus = node;
          }
          if (
            node.type === "topic" &&
            (toFocus == null ||
              (toFocus.type === "topic" && node.value > toFocusValue))
          ) {
            toFocusValue = node.value;
            toFocus = node;
          }
        });
        if (toFocus == null) return;

        const targetX = (toFocus as TopicCloudPoint).x ?? 0;
        const targetY = (toFocus as TopicCloudPoint).y ?? 0;
        const transform = d3.zoomIdentity
          .translate((width - 20) / 2, (height - 20) / 2)
          .scale(0.7)
          .translate(-targetX + 40, -targetY - 40);

        svg
          .transition()
          .duration(750)
          .call(zoomBehaviorRef.current!.transform as any, transform);
      });

    const zoomBehavior: ZoomBehavior<SVGSVGElement, unknown> = zoom<
      SVGSVGElement,
      unknown
    >().on("zoom", (event) => {
      g.attr("transform", event.transform);
    });
    svg.call(zoomBehavior as any);
    zoomBehaviorRef.current = zoomBehavior;

    return () => {
      simulation.stop();
      svg.selectAll("*").remove();
    };
  }, [data, fontScales, onWordClick]);

  useEffect(() => {
    if (!svgRef.current || !colorScales) return;
    const svg = d3.select(svgRef.current);
    svg
      .selectAll<SVGTextElement, TopicCloudPoint>(".node-label")
      .attr("stroke", (d) => colorScales[d.type](0))
      .style("transition", "fill 0.3s ease") // Optional smooth fade between themes
      .style("fill", (d) => colorScales[d.type](d.value));

    svg
      .select(".concept-path")
      .style("fill", () =>
        theme === "dark" ? "rgba(255,255,255,0.1)" : "rgba(100,100,100,0.1)",
      )
      .style("opacity", 0.5);
  }, [theme, colorScales, data]);

  useEffect(() => {
    if (!svgRef.current || !colorScales) return;
    const svg = d3.select(svgRef.current);
    const term = searchTerm.trim().toLowerCase();
    let bestMatch: TopicCloudPoint | null = null;

    const toHighlight = new Set(
      data.points
        .filter(
          (point) =>
            (point.original ?? point.text).includes(searchTerm) ||
            point.id.includes(searchTerm),
        )
        .map((point) => point.id),
    );

    svg
      .selectAll<SVGTextElement, TopicCloudPoint>(".node-label")
      .attr("stroke-opacity", (d) => (term === d.id ? 1 : 0))
      .style("transition", "opacity 0.2s ease, filter 0.2s ease")
      .style("opacity", (d) => {
        if (!term) return 1;

        const target = d.original ?? d.text;
        const isMatch = target.toLowerCase() === term;

        // If it's a match, see if it has a higher value than our current best match
        if (isMatch) {
          bestMatch = d;
        }

        return isMatch || toHighlight.has(d.id) ? 1 : 0.2;
      })
      .style("filter", (d) => {
        if (!term) return "none";
        return toHighlight.has(d.id) ? "none" : "grayscale(50%)";
      });

    if (term && bestMatch) {
      // Extract the coordinates (fallback to 0)
      const targetX = (bestMatch as TopicCloudPoint).x ?? 0;
      const targetY = (bestMatch as TopicCloudPoint).y ?? 0;

      // Use the same coordinate space size as your physics engine
      const width = dimensions.width;
      const height = dimensions.height;

      // Calculate the transform: Move to center, apply scale, reverse by target coordinates
      const transform = d3.zoomIdentity
        .translate(width / 2, height / 2)
        .scale(0.7)
        .translate(-targetX, -targetY);
      setHoveredNode(bestMatch as TopicCloudPoint);
      svg
        .transition()
        .duration(750)
        .call(zoomBehaviorRef.current!.transform as any, transform)
        .on("end", () => {
          // Because the camera centered the node, it is exactly at 50% / 50%
          select(actionRef.current)
            .style("visibility", "visible")
            .style("opacity", 1)
            .style("left", "calc(50% + 30px)")
            .style("top", "calc(50% + 20px)");
        });
    }
  }, [searchTerm]);

  useEffect(() => {
    if (
      hoveredNode == null ||
      actionRef.current == null ||
      wrapperRef.current == null
    )
      return;

    const bounds = (
      wrapperRef.current as HTMLDivElement
    ).getBoundingClientRect();

    const actionBounds = (
      actionRef.current as HTMLDivElement
    ).getBoundingClientRect();
    const actionRight = actionBounds.right - bounds.left;
    const actionBottom = actionBounds.bottom - bounds.top;
    const actionLeft = actionBounds.left - bounds.left;
    const actionTop = actionBounds.top - bounds.top;

    if (actionRight > bounds.right) {
      actionRef.current.style.left = `${actionLeft - (actionRight - actionLeft) - 10}px`;
    }
    if (actionBottom > bounds.height) {
      actionRef.current.style.top = `${
        actionTop - (actionBottom - actionTop) - 10
      }px`;
    }
    actionRef.current.style.visibility = "visible";
    actionRef.current.style.opacity = "1";
  }, [hoveredNode]);

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
    const width = 1000; //wrapperRef.current?.clientWidth ?? 800;
    const height = 1000; //wrapperRef.current?.clientHeight ?? 800;
    svg
      .transition()
      .duration(500)
      .call(zoomBehaviorRef.current!.translateTo as any, width / 2, height / 2);
  };

  return (
    <div ref={wrapperRef} className="relative min-h-0 w-full flex-1 grow">
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
      <div className="flex min-h-0 flex-1">
        <svg
          ref={svgRef}
          className={cn(
            "m-auto h-full w-full transition-opacity duration-300 ease-in",
          )}
          preserveAspectRatio="xMidYMid meet"
        />
      </div>
      <div
        ref={actionRef}
        className="bg-card/80 absolute flex max-h-70 w-70 flex-col gap-2 overflow-hidden rounded-lg border shadow-sm backdrop-blur-md"
      >
        <HoverDiv hoveredNode={hoveredNode} />
      </div>
    </div>
  );
};

const HoverDiv = ({ hoveredNode }: { hoveredNode: TopicCloudPoint | null }) => {
  if (hoveredNode == null) return null;
  return (
    <>
      <div className="h-fit border-b pb-2 text-center text-sm font-bold text-wrap">
        {hoveredNode.original ?? hoveredNode.text}
      </div>
      <div className="flex items-center justify-between">
        <div className="flex flex-col">
          <h3 className="text-muted-foreground flex items-center gap-2 text-xs">
            {hoveredNode.type === "topic" ? (
              <ChartNoAxesGanttIcon className="size-3" />
            ) : (
              <MessageSquareIcon className="size-3" />
            )}
            {capitalize(hoveredNode.type)}
          </h3>
          <h3 className="text-muted-foreground flex items-center gap-2 text-xs">
            <FileIcon className="size-3" />
            <div>{hoveredNode?.value} Documents</div>
          </h3>
        </div>
        <div className="flex items-center gap-2">
          <Hint hint="Search for related information">
            <Link
              href={formatURL("/search", {
                tid: hoveredNode.type === "topic" ? hoveredNode.id : undefined,
                cid:
                  hoveredNode.type === "concept" ? hoveredNode.id : undefined,
                placeholder: `${capitalize(hoveredNode.type)}: ${hoveredNode.original ?? hoveredNode.text}`,
              })}
              className={buttonVariants({
                variant: "listButton",
                size: "icon-sm",
              })}
            >
              <SearchIcon />
            </Link>
          </Hint>
          <Hint hint={`View ${capitalize(hoveredNode.type)} information`}>
            <Link
              href={formatURL("/search", {
                tid: hoveredNode.type === "topic" ? hoveredNode.id : undefined,
                cid:
                  hoveredNode.type === "concept" ? hoveredNode.id : undefined,
                placeholder: `${capitalize(hoveredNode.type)}: ${hoveredNode.original ?? hoveredNode.text}`,
              })}
              className={buttonVariants({
                variant: "listButton",
                size: "icon-sm",
              })}
            >
              <BinocularsIcon />
            </Link>
          </Hint>
        </div>
      </div>
      <div className="flex min-h-0 flex-col gap-2">
        <div className="border-y py-1 text-sm font-medium">
          {hoveredNode.type === "topic" ? "Concepts" : "Instances"}
        </div>
        <div className="scrollable flex flex-1 flex-col gap-1 text-xs">
          {hoveredNode &&
            Object.keys(hoveredNode.subvalues).map((kw) => (
              <div key={kw}>{kw}</div>
            ))}
        </div>
      </div>
    </>
  );
};
