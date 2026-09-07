"use client";
import { Button } from "@/components/ui/button";
import React from "react";
import { useTopicsTabParams } from "@/features/analytics/hooks/useTopicsTabParams";
import { useCohortsParams } from "@/features/analytics/hooks/useCohortsParams";

export const CohortsPageTabs = () => {
  const [params, setParams] = useCohortsParams();
  return (
    <div className="flex w-full items-center justify-start p-2">
      <Button
        onClick={() => setParams({ tab: "list" })}
        className="rounded-r-none"
        variant={params.tab === "list" ? "default" : "outline"}
      >
        List
      </Button>
      <Button
        onClick={() => setParams({ tab: "chart" })}
        className="rounded-l-none"
        variant={params.tab === "chart" ? "default" : "outline"}
      >
        Cohort Graph
      </Button>
    </div>
  );
};
