import { Button } from "@/components/ui/button";
import React from "react";
import { parseAsStringEnum, useQueryState } from "nuqs";

export const Tabs = () => {
  const [tab, setTab] = useQueryState(
    "tab",
    parseAsStringEnum(["list", "chart"])
      .withDefault("list")
      .withOptions({ clearOnDefault: true }),
  );
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
        Similarity Graph
      </Button>
    </div>
  );
};
