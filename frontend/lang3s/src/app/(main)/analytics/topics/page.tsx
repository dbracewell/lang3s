import { caller } from "@/lib/trpc/server";
import React, { Suspense } from "react";
import { TopicsListView } from "@/features/analytics/ui/components/TopicsListView";
import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import { TopicsPageTabs } from "@/features/analytics/ui/components/TopicsPageTabs";
import { TopicsGraph } from "@/features/analytics/ui/components/TopicsGraph";
import { Skeleton } from "@/components/ui/skeleton";

const TopicsPage = async () => {
  return (
    <ScrollableBox.Container className="m-1 gap-3">
      <div className="flex flex-col">
        <h1>Topics</h1>
        <p className="pageSubheading">
          The recurring themes discovered within the corpus
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
  const data = await caller.analytics.getTopics();
  return (
    <>
      <TopicsPageTabs />
      <TopicsListView points={data.points} />
      <TopicsGraph data={data} />
    </>
  );
};

export default TopicsPage;
