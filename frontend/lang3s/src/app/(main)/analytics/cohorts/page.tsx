"use client";

import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import React, { Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { CohortsPageTabs } from "@/features/analytics/ui/components/CohortsPageTabs";
import { CohortsGraph } from "@/features/analytics/ui/components/CohortsGraph";
import { CohortsList } from "@/features/analytics/ui/components/CohortsList";
import { useQuery } from "@tanstack/react-query";
import { cohortsOptions } from "@/clients/analytics/@tanstack/react-query.gen";
import { analyticsClient } from "@/lib/api";
import { CohortClustering } from "@/clients/analytics";

const CohortsPage = () => {
  const { data } = useQuery({
    ...cohortsOptions({
      client: analyticsClient,
    }),
  });
  return (
    <ScrollableBox.Container className="@container relative gap-3">
      <div className="flex flex-col">
        <h1>Cohorts</h1>
        <p className="pageSubheading">
          Groups of entities commonly appearing together in the same documents
        </p>
      </div>
      <Suspense fallback={<SkeletonPage />}>
        {data == null ? <SkeletonPage /> : <Section data={data} />}
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

const Section = ({ data }: { data: CohortClustering }) => {
  return (
    <>
      <CohortsPageTabs />
      <CohortsList clusters={data.clusters} />
      <CohortsGraph data={data} />
    </>
  );
};

export default CohortsPage;
