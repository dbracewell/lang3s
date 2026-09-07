import type {
  ForceGraphPoint,
  ForceGraphSimilarity,
  SimulatorProps,
} from "@/components/d3/ForceGraph/types";
import {
  forceCollide,
  forceLink,
  forceManyBody,
  forceX,
  forceY,
} from "d3-force";
import { selectSVGElement } from "@/components/d3/functions";

export const getNodeElement = <Point extends ForceGraphPoint>(
  svg: SVGSVGElement,
) => {
  return selectSVGElement<SVGElement, Point>(svg, "circle");
};

export const getLinkElement = <Point extends ForceGraphPoint>(
  svg: SVGSVGElement,
) => {
  return selectSVGElement<SVGLineElement, ForceGraphSimilarity<Point>>(
    svg,
    "line",
  );
};

export const getTextElement = <Point extends ForceGraphPoint>(
  svg: SVGSVGElement,
) => {
  return selectSVGElement<SVGTextElement, Point>(svg, ".node-label");
};

export const defaultSimulator = <Point extends ForceGraphPoint>({
  simulation,
  links,
  width,
  height,
  colliderFn,
  svg,
}: SimulatorProps<Point>) => {
  const linkElement = getLinkElement(svg);
  const nodeElement = getNodeElement(svg);
  const textElement = getTextElement(svg);
  simulation
    .force("x", forceX<Point>(() => width / 2).strength(0.08))
    .force("y", forceY<Point>(() => height / 2).strength(0.08))
    .force(
      "link",
      forceLink<Point, ForceGraphSimilarity<Point>>(links)
        .id((d: Point) => d.id)
        .distance((d) => Math.max(10, (1 - d.similarity) * 100))
        .strength(0.25),
    )
    .force("charge", forceManyBody().strength(-40))
    .force(
      "collide",
      forceCollide<Point>().radius((d) =>
        colliderFn ? colliderFn(d) : (d.r ?? 10) * 4,
      ),
    )
    .on("tick", () => {
      linkElement
        .attr("x1", (d) => d.source.x ?? 0)
        .attr("y1", (d) => d.source.y ?? 0)
        .attr("x2", (d) => d.target.x ?? 0)
        .attr("y2", (d) => d.target.y ?? 0);
      nodeElement.attr("cx", (d) => d.x ?? 0).attr("cy", (d) => d.y ?? 0);
      textElement.attr("transform", (d) => `translate(${d.x},${d.y})`);
    });
};
