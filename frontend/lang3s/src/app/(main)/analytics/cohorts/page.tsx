import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import React, { Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { caller } from "@/lib/trpc/server";
import { CohortsPageTabs } from "@/features/analytics/ui/components/CohortsPageTabs";
import { CohortsGraph } from "@/features/analytics/ui/components/CohortsGraph";
import { CohortsList } from "@/features/analytics/ui/components/CohortsList";

const CohortsPage = async () => {
  return (
    <ScrollableBox.Container className="relative gap-3">
      <div className="flex flex-col">
        <h1>Cohorts</h1>
        <p className="pageSubheading">
          Groups of entities commonly appearing together in the same documents
        </p>
      </div>
      <Suspense fallback={<SkeletonPage />}>
        <Section />
      </Suspense>
    </ScrollableBox.Container>
  );
};

const SkeletonPage = () => {
  return (
    <>
      <Skeleton className="h-10 w-sm" />
      <Skeleton className="h-full w-full" />
    </>
  );
};

const Section = async () => {
  const data = await caller.analytics.getCohorts();
  return (
    <>
      <CohortsPageTabs />
      <CohortsList clusters={data.clusters} />
      <CohortsGraph
        data={{ points: data.points, similarities: data.similarities }}
      />
    </>
  );
};

export default CohortsPage;
