import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import React, { Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { CorpusMapRouter } from "@/features/analytics/ui/components/CorpusMap";
import { CorpusMapTabs } from "@/features/analytics/ui/components/CorpusMapTabs";

const Page = () => {
  return (
    <ScrollableBox.Container className="m-1 gap-3">
      <ScrollableBox.Header>
        <h1>Corpus Explorer</h1>
        <p className="pageSubheading">
          Interactive exploration of the topics, concepts, and claims presented
          in the corpus.
        </p>
      </ScrollableBox.Header>
      <Suspense fallback={<SkeletonPage />}>
        <Section />
      </Suspense>
    </ScrollableBox.Container>
  );
};

const SkeletonPage = () => {
  return (
    <>
      <Skeleton className="mr-1 h-13 w-50" />
      <Skeleton className="h-12 w-md" />
      <Skeleton className="h-full w-full" />
    </>
  );
};

const Section = async () => {
  return (
    <div className="flex max-h-full min-h-0 flex-1 flex-col gap-4">
      <CorpusMapTabs />
      <CorpusMapRouter />
      {/*<TopicTree tree={tree} />*/}
    </div>
  );
};

export default Page;
