"use client";
import { Button } from "@/components/ui/button";
import React from "react";
import { useTabParams } from "@/features/search/hooks/useTabParams";

export const SearchTabButtons = () => {
  const [tab, setTab] = useTabParams();
  return (
    <div className="flex w-full items-center justify-start p-2">
      <Button
        onClick={() => setTab("docs")}
        className="rounded-r-none"
        variant={tab === "docs" ? "default" : "outline"}
      >
        Documents
      </Button>
      <Button
        onClick={() => setTab("annotations")}
        className="rounded-none border-x-0"
        variant={tab === "annotations" ? "default" : "outline"}
      >
        Annotations
      </Button>
      <Button
        onClick={() => setTab("topics")}
        className="rounded-l-none"
        variant={tab === "topics" ? "default" : "outline"}
      >
        Topics
      </Button>
    </div>
  );
};
