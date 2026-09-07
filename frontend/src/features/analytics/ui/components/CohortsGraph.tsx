"use client";
import React, { useCallback } from "react";
import { useCohortsParams } from "@/features/analytics/hooks/useCohortsParams";
import {
  ForceGraphMouseEventProps,
  ForceGraphPoint,
  ForceGraphSimilarity,
} from "@/components/d3/ForceGraph/types";
import { D3ContextProvider } from "@/components/d3/D3ContextType";
import { ForceGraph } from "@/components/d3/ForceGraph";
import {
  getLinkElement,
  getNodeElement,
  getTextElement,
} from "@/components/d3/ForceGraph/functions";
import { NavigationBar } from "@/components/d3/NavigationBar";
import { CohortClustering } from "@/clients/analytics";

export type CohortPoint = ForceGraphPoint & {
  cid: string;
};
const styleFn = (svg: SVGSVGElement) => {
  getNodeElement(svg)
    .style("fill", (d: ForceGraphPoint) => d.color!)
    .attr("r", (d: ForceGraphPoint) => d.r ?? 20);

  getLinkElement(svg)
    .attr("opacity", 1)
    .attr("stroke", "var(--color-border)")
    .attr(
      "stroke-width",
      (d: ForceGraphSimilarity<ForceGraphPoint>) => d.similarity * 10,
    );
};

const onMouseEnter = ({
  getRef,
  point,
}: ForceGraphMouseEventProps<CohortPoint>) => {
  const svg = getRef("svg").current;
  if (svg != null) {
    getNodeElement<CohortPoint>(svg)
      .attr("filter", (d) => (d.cid === point.cid ? "none" : "grayscale(50%)"))
      .attr("opacity", (d) => (d.cid === point.cid ? 1.0 : 0.2));

    getTextElement<CohortPoint>(svg)
      .attr("opacity", (d) => (d.cid === point.cid ? 1.0 : 0.2))
      .style("font-size", (d) => (d.cid === point.cid ? 18 : 14))
      .style("font-weight", (d) => (d.cid === point.cid ? 700 : 400));

    getLinkElement<CohortPoint>(svg).attr("opacity", (d) =>
      d.source.cid === point.cid ? 1.0 : 0.2,
    );
  }

  return true;
};

const onMouseOut = ({ getRef }: ForceGraphMouseEventProps<CohortPoint>) => {
  const svg = getRef("svg").current;
  if (svg == null) return true;
  getNodeElement(svg).attr("filter", "none").attr("opacity", 1);
  getTextElement(svg)
    .attr("opacity", 1)
    .style("font-size", 14)
    .style("font-weight", 400);
  getLinkElement(svg).attr("opacity", 1);
  return true;
};

export const CohortsGraph = ({ data }: { data: CohortClustering }) => {
  const [params, setParams] = useCohortsParams();

  const onMouseClick = useCallback(
    ({ point }: ForceGraphMouseEventProps<CohortPoint>) => {
      setParams({ q: point.text, tab: "list" });
      return true;
    },
    [setParams],
  );

  if (params.tab !== "chart") {
    return null;
  }

  return (
    <D3ContextProvider>
      <ForceGraph
        svgClassName="rounded-lg"
        points={data.points as CohortPoint[]}
        similarities={data.similarities}
        styleFn={styleFn}
        textSplitlines={true}
        onMouseEnter={onMouseEnter}
        onMouseClick={onMouseClick}
        onMouseOut={onMouseOut}
        nodeClassName="cursor-pointer"
        textClassName="fill-foreground text-sm text-select-none pointer-events-none"
      >
        <NavigationBar className="top-2 right-2" />
      </ForceGraph>
    </D3ContextProvider>
  );
};
