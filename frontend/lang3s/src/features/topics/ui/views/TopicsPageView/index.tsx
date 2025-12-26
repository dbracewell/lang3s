"use client";

import { BubbleChart } from "@/components/charts/BubbleChart";
import React from "react";
import { useTheme } from "next-themes";
import { parseAsStringEnum, useQueryState } from "nuqs";
import { ListView } from "@/features/topics/ui/views/TopicsPageView/ListView";
import { Tabs } from "@/features/topics/ui/views/TopicsPageView/Tabs";
import { ScrollableBox } from "@/components/scrolling/Scrollbox";

type DataProps = {
  data: {
    points: { id: string; name: string; support: number }[];
    similarities: { id1: string; id2: string; similarity: number }[];
  };
};

export const TopicsPageView = ({ data }: DataProps) => {
  const theme = useTheme();
  const [tab] = useQueryState(
    "tab",
    parseAsStringEnum(["list", "chart"])
      .withDefault("list")
      .withOptions({ clearOnDefault: true }),
  );
  return (
    <ScrollableBox.Container className="gap-3">
      <div className="flex flex-col">
        <h1>Topics</h1>
        <p className="pageSubheading">The topics discussed in the corpus.</p>
      </div>
      <Tabs />
      {tab == "list" ? (
        <ScrollableBox.ScrollArea outerClassName="p-0!">
          <div className="bg-heading sticky top-0 grid grid-cols-1 gap-2 text-white md:grid-cols-[3fr_2fr]">
            <div className="px-5 py-0.5 font-semibold">Topic Name</div>
            <div className="hidden px-5 py-0.5 font-semibold md:block">
              Relative Support
            </div>
          </div>
          <ListView points={data.points} />
        </ScrollableBox.ScrollArea>
      ) : (
        <BubbleChart
          data={data}
          showLabels={true}
          splitLabels=", "
          onNodeClick={(node) => alert(`Clicked: ${node.name}`)}
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
      )}
    </ScrollableBox.Container>
  );
};
