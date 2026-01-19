"use client";

import { useGlobalSearchParams } from "@/features/search/hooks/useSearchParams";
import { Activity, Suspense } from "react";
import { DocumentSearchView } from "@/features/search/ui/views/DocumentSearchView";
import { AnnotationSearchView } from "@/features/search/ui/views/AnnotationSearchView";
import { TopicSearchView } from "@/features/search/ui/views/TopicsSearchView";
import { Spinner } from "@/components/Spinner";

export const SearchTabList = () => {
  const [searchParams] = useGlobalSearchParams();
  return (
    <>
      <Activity
        key="docs"
        mode={searchParams.tab === "docs" ? "visible" : "hidden"}
      >
        <Suspense fallback={<Spinner />}>
          <DocumentSearchView />
        </Suspense>
      </Activity>
      <Activity
        key="annotations"
        mode={searchParams.tab === "annotations" ? "visible" : "hidden"}
      >
        <Suspense fallback={<Spinner />}>
          <AnnotationSearchView />
        </Suspense>
      </Activity>
      <Activity
        key="topics"
        mode={searchParams.tab === "topics" ? "visible" : "hidden"}
      >
        <Suspense fallback={<Spinner />}>
          <TopicSearchView />
        </Suspense>
      </Activity>
    </>
  );
};
