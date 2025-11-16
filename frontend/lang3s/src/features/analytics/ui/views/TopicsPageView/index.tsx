"use client";

import {
  BubbleChart,
  Point,
  Similarity,
} from "@/components/charts/BubbleChart";
import { Button } from "@/components/ui/button";
import React, { useState } from "react";

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
  const [state, setState] = useState<"list" | "chart">("list");
  return (
    <div className="flex h-full min-h-0 flex-1 flex-col items-center overflow-clip rounded border bg-white p-5 shadow">
      <div className="flex w-full items-center justify-start p-2">
        <Button
          onClick={() => setState("list")}
          className="rounded-r-none"
          variant={state === "list" ? "default" : "outline"}
        >
          List
        </Button>
        <Button
          onClick={() => setState("chart")}
          className="rounded-l-none"
          variant={state === "chart" ? "default" : "outline"}
        >
          Chart
        </Button>
      </div>
      {state == "list" ? (
        <div className="scrollable w-full flex-1">
          {data.points
            .sort((a, b) => b.support - a.support)
            .map((topic) => (
              <div key={topic.id} className="p-2 odd:bg-slate-100">
                {topic.name} ({topic.support})
              </div>
            ))}
        </div>
      ) : (
        <BubbleChart
          data={data}
          showLabels={false}
          onNodeClick={(node) => alert(`Clicked: ${node.name}`)}
          styles={{
            backgroundColor: "transparent",
            nodeFill: (n) => (n.support > 50 ? "#3b82f6" : "#93c5fd"),
            centerNodeColor: "#f59e0b",
            linkColor: "transparent",
            tooltipBg: "#111827",
            tooltipTextColor: "#f9fafb",
          }}
          className="flex-1"
        />
      )}
    </div>
  );
};
