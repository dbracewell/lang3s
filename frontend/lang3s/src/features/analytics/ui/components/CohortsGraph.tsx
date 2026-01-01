"use client";
import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import { useTabParams } from "@/features/analytics/hooks/useTabParams";
import { ForceGraph, Point, Similarity } from "@/components/charts/ForceGraph";
import React from "react";
import { parseAsString, useQueryState } from "nuqs";

export const CohortsGraph = ({
  data,
}: {
  data: {
    points: Point[];
    similarities: Omit<Similarity, "source" | "target">[];
  };
}) => {
  const [tabs, setTabs] = useTabParams();
  const [, setSearchQuery] = useQueryState(
    "q",
    parseAsString.withDefault("").withOptions({ clearOnDefault: true }),
  );
  if (tabs !== "chart") {
    return null;
  }
  return (
    <ForceGraph
      data={data}
      linkScaleFactor={2}
      showLabels={true}
      minSupportToShowLabel={5}
      onNodeClick={async (node) => {
        await setSearchQuery(node.name);
        setTabs("list");
      }}
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
