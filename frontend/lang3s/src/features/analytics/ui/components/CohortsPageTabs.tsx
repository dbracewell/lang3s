"use client";
import { Button } from "@/components/ui/button";
import React from "react";
import { useTabParams } from "@/features/analytics/hooks/useTabParams";

export const CohortsPageTabs = () => {
  const [tab, setTab] = useTabParams();
  return (
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
        Cohort Graph
      </Button>
    </div>
  );
};
