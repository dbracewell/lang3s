"use client";
import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import { useTopicsTabParams } from "@/features/analytics/hooks/useTopicsTabParams";
import { ForceGraph, Point, Similarity } from "@/components/charts/ForceGraph";
import React from "react";
import { parseAsString, useQueryState } from "nuqs";
import { useCohortsParams } from "@/features/analytics/hooks/useCohortsParams";

export const CohortsGraph = ({
  data,
}: {
  data: {
    points: Point[];
    similarities: Omit<Similarity, "source" | "target">[];
  };
}) => {
  const [params, setParams] = useCohortsParams();
  if (params.tab !== "chart") {
    return null;
  }
  return (
    <ForceGraph
      data={data}
      linkScaleFactor={2}
      showLabels={true}
      minSupportToShowLabel={5}
      onNodeClick={async (node) => {
        await setParams({ q: node.name, tab: "list" });
      }}
      styles={{
        labelFontSize: 10,
        labelColor: "var(--color-foreground)",
        backgroundColor: "transparent",
        linkOpacity: 1,
        linkColor: "var(--color-border)",
      }}
    />
  );
};
