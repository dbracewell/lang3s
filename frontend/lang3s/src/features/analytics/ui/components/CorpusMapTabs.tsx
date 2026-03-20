"use client";
import { Button } from "@/components/ui/button";
import React from "react";
import { parseAsStringEnum, useQueryState } from "nuqs";
import { useTopicsTabParams } from "@/features/analytics/hooks/useTopicsTabParams";
import { useCorpusMapParams } from "@/features/analytics/hooks/useCorpusMapParams";

export const CorpusMapTabs = () => {
  const [params, setParams] = useCorpusMapParams();
  return (
    <div className="flex w-full items-center justify-start p-2">
      <Button
        onClick={() => setParams({ tab: "chart" })}
        className="rounded-r-none"
        variant={params.tab === "chart" ? "default" : "outline"}
      >
        Visual Explorer
      </Button>
      <Button
        onClick={() => setParams({ tab: "list" })}
        className="rounded-l-none"
        variant={params.tab === "list" ? "default" : "outline"}
      >
        List
      </Button>
    </div>
  );
};
