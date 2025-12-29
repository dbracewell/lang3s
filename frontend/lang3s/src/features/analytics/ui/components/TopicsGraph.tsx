"use client";
import { ForceGraph } from "@/components/charts/ForceGraph";
import React from "react";
import { useTheme } from "next-themes";
import { useRouter } from "next/navigation";
import { useTopicsTab } from "@/features/analytics/hooks/useTopicsTab";

type DataProps = {
  data: {
    points: { id: string; name: string; support: number }[];
    similarities: { id1: string; id2: string; similarity: number }[];
  };
};

export const TopicsGraph = ({ data }: DataProps) => {
  const theme = useTheme();
  const [tab] = useTopicsTab();
  const router = useRouter();
  if (tab === "list") {
    return null;
  }
  return (
    <ForceGraph
      data={data}
      showLabels={true}
      splitLabels=", "
      onNodeClick={(node) => router.push(`/analytics/topics/${node.id}`)}
      styles={{
        backgroundColor: "transparent",
        nodeFill: (n) =>
          n.support > 50
            ? "var(--color-dodger-blue-500)"
            : "var(--color-dodger-blue-200)",
        centerNodeColor: "#f59e0b",
        linkColor: "transparent",
        tooltipBg: "#111827",
        tooltipTextColor: "#f9fafb",
        labelFontSize: 10,
        labelColor: theme.theme === "dark" ? "#fff" : "#000",
      }}
      className="flex-1"
    />
  );
};
