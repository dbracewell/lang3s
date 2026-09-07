"use client";
import { InfiniteScroll } from "@/components/scrolling/InfiniteScroll";
import { DocumentScrollHeader } from "@/components/scrolling/DocumentScrollHeader";
import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import { DocumentResult } from "@/features/documents/ui/components/DocumentResult";
import { Skeleton } from "@/components/ui/skeleton";
import { useScrollToTop } from "@/hooks/useScrollToTop";
import { useEffect } from "react";
import { useChatContext } from "@/features/chat/hooks/useChatContext";
import { useInfiniteQuery } from "@tanstack/react-query";
import { documentsGetAllInfiniteOptions } from "@/clients/core/@tanstack/react-query.gen";
import { coreClient } from "@/lib/api";

export const DocumentsViewPage = () => {
  const { isScrolled, onScroll, scrollRef } = useScrollToTop();
  const { setContext } = useChatContext();
  const {
    data: docs,
    isFetchingNextPage,
    error,
    hasNextPage,
    fetchNextPage,
  } = useInfiniteQuery({
    ...documentsGetAllInfiniteOptions({
      client: coreClient,
    }),
    getNextPageParam: (lastPage) => lastPage.next_cursor as number,
    initialPageParam: 1,
  });

  useEffect(() => {
    if (docs != null) {
      const ctxt = docs.pages
        .flatMap((p) => p.items)
        .map((p) => `DocumentId: ${p.id} Content:${p.snippet}`)
        .join("\n");
      setContext(ctxt);
    }
  }, [docs, setContext]);

  // useEffect(() => {
  //   const t = async () => {
  //     const docs = await new ApiClient({
  //       client: coreClient,
  //     }).documentsGetAll();
  //     console.log(docs);
  //   };
  //   t();
  // }, []);

  if (error) {
    throw error;
  }

  if (docs == null) {
    return <DocumentsViewPageSkeleton />;
  }

  return (
    <>
      <DocumentScrollHeader
        count={docs?.pages[0].total ?? 0}
        scrollRef={scrollRef}
        isScrolled={isScrolled}
      />
      <ScrollableBox.ScrollArea
        ref={scrollRef}
        onScroll={onScroll}
        outerClassName="p-0!"
        className="bg-card min-h-full flex-1"
      >
        {docs?.pages
          .flatMap((page) => page.items)
          .map((doc) => (
            <DocumentResult doc={doc} key={doc.id} />
          ))}
        <InfiniteScroll
          fetchNextPage={fetchNextPage}
          isFetchingNextPage={isFetchingNextPage}
          hasNextPage={hasNextPage}
        />
      </ScrollableBox.ScrollArea>
    </>
  );
};

export const DocumentsViewPageSkeleton = () => {
  return (
    <>
      <Skeleton className="h-10 w-full rounded-lg border pb-10" />
      <Skeleton className="flex-1 rounded-lg border" />
    </>
  );
};
