"use client";
import { ForceGraph, Point, Similarity } from "@/components/charts/ForceGraph";
import React from "react";
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
      minSupportToShowLabel={25}
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
