"use client";

import {
  BubbleChart,
  Point,
  Similarity,
} from "@/components/charts/BubbleChart";
import { Button } from "@/components/ui/button";
import React, { useMemo, useState } from "react";
import { useTheme } from "next-themes";
import { SearchIcon } from "lucide-react";
import { Hint } from "@/components/hint";
import { parseAsString, parseAsStringEnum, useQueryState } from "nuqs";

const data = {
  points: [
    { id: "a", name: "Alpha", support: 120 },
    { id: "b", name: "Bravo", support: 80 },
    { id: "c", name: "Charlie", support: 60 },
    { id: "d", name: "Delta", support: 40 },
    { id: "e", name: "Echo", support: 20 },
  ],
  similarities: [
    { id1: "a", id2: "b", similarity: 0.9 },
    { id1: "a", id2: "c", similarity: 0.7 },
    { id1: "a", id2: "d", similarity: 0.4 },
    { id1: "a", id2: "e", similarity: 0.2 },
    { id1: "b", id2: "c", similarity: 0.8 },
    { id1: "b", id2: "d", similarity: 0.5 },
    { id1: "b", id2: "e", similarity: 0.3 },
    { id1: "c", id2: "d", similarity: 0.6 },
    { id1: "c", id2: "e", similarity: 0.4 },
    { id1: "d", id2: "e", similarity: 0.7 },
  ],
};

type DataProps = {
  data: {
    points: { id: string; name: string; support: number }[];
    similarities: { id1: string; id2: string; similarity: number }[];
  };
};

export const TopicsPageView = ({ data }: DataProps) => {
  const total = useMemo(
    () => Math.max(...data.points.map((p) => p.support)),
    [data.points],
  );
  const theme = useTheme();
  const [tab, setTab] = useQueryState(
    "tab",
    parseAsStringEnum(["list", "chart"])
      .withDefault("list")
      .withOptions({ clearOnDefault: true }),
  );
  return (
    <div className="flex h-full min-h-0 flex-1 flex-col items-start gap-2 p-2">
      <h1 className="pb-2">Topics discussed in the corpus</h1>
      <div className="flex w-full items-center justify-start p-2">
        <Button
          onClick={() => setTab("list")}
          className="rounded-r-none"
          variant={tab === "list" ? "default" : "outline"}
        >
          List
        </Button>
        <Button
          onClick={() => setTab("chart")}
          className="rounded-l-none"
          variant={tab === "chart" ? "default" : "outline"}
        >
          Similarity Graph
        </Button>
      </div>
      {tab == "list" ? (
        <div className="scrollable w-full flex-1 pr-2">
          <div className="overflow-clip rounded-lg border">
            <table className="w-full">
              <thead>
                <tr className="bg-heading text-white">
                  <th className="p-0.5"></th>
                  <th className="p-0.5">Topic Name</th>
                  <th className="hidden p-0.5 md:block">Relative Support</th>
                </tr>
              </thead>
              <tbody>
                {data.points
                  .sort((a, b) => b.support - a.support)
                  .map((topic) => (
                    <tr key={topic.id} className="odd:bg-alternate-row bg-row">
                      <td className="p-1">
                        <Hint hint="Search the corpus for this topic" asChild>
                          <Button size="icon-xs" variant="ghost">
                            <SearchIcon />
                          </Button>
                        </Hint>
                      </td>
                      <td className="p-1">{topic.name}</td>
                      <td className="hidden p-1 md:table-cell">
                        <div
                          className="bg-dodger-blue-500 h-1 justify-self-center"
                          style={{
                            width: `${Math.max(5, (topic.support / total) * 350)}px`,
                          }}
                        />
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
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
    </div>
  );
};
