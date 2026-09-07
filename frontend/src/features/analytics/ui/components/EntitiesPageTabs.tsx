"use client";
import { useEntitySearchParams } from "@/features/analytics/hooks/useEntitySearchParams";
import React, { Activity, Suspense } from "react";
import { Spinner } from "@/components/Spinner";
import { TopEntitiesList } from "@/features/analytics/ui/components/TopEntitiesList";
import { EntityMetrics } from "@/features/analytics/ui/components/EntityMetrics";
import { Button } from "@/components/ui/button";

export const EntitiesPageTabs = () => {
  const [params] = useEntitySearchParams();
  return (
    <>
      <Tabs />
      <Activity key="docs" mode={params.view === "list" ? "visible" : "hidden"}>
        <Suspense fallback={<Spinner />}>
          <TopEntitiesList />
        </Suspense>
      </Activity>
      <Activity
        key="annotations"
        mode={params.view === "metrics" ? "visible" : "hidden"}
      >
        <Suspense fallback={<Spinner />}>
          <EntityMetrics />
        </Suspense>
      </Activity>
    </>
  );
};

const Tabs = () => {
  const [params, setParams] = useEntitySearchParams();
  return (
    <div className="flex w-full items-center justify-start p-2">
      <Button
        onClick={() => setParams({ view: "list" })}
        className="rounded-r-none"
        variant={params.view === "list" ? "default" : "outline"}
      >
        List
      </Button>
      <Button
        onClick={() => setParams({ view: "metrics" })}
        className="rounded-l-none"
        variant={params.view === "metrics" ? "default" : "outline"}
      >
        Insights
      </Button>
    </div>
  );
};
