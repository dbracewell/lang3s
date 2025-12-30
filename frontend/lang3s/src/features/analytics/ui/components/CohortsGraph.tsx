"use client";
import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import { useTabParams } from "@/features/analytics/hooks/useTabParams";
import { ForceGraph, Point, Similarity } from "@/components/charts/ForceGraph";
import React from "react";

export const CohortsGraph = ({
  data,
}: {
  data: {
    points: Point[];
    similarities: Omit<Similarity, "source" | "target">[];
  };
}) => {
  const [tabs] = useTabParams();

  if (tabs !== "chart") {
    return null;
  }
  return (
    <ForceGraph
      data={data}
      linkScaleFactor={2}
      showLabels={true}
      minSupportToShowLabel={5}
      styles={{
        labelFontSize: 12,
        labelColor: "var(--color-foreground)",
        backgroundColor: "transparent",
        linkOpacity: 1,
        linkColor: "var(--color-border)",
      }}
    />
  );
};
