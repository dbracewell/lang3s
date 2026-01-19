"use client";
import { InfiniteScroll } from "@/components/scrolling/InfiniteScroll";
import { useTRPCSuspenseInfiniteQuery } from "@/lib/trpc/use-queries";
import { DocumentScrollHeader } from "@/components/scrolling/DocumentScrollHeader";
import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import { DocumentResult } from "@/features/documents/ui/components/DocumentResult";
import { Skeleton } from "@/components/ui/skeleton";
import { useScrollToTop } from "@/hooks/useScrollToTop";
import { useContext, useEffect } from "react";
import { useChatContext } from "@/features/chat/hooks/useChatContext";

export const DocumentsViewPage = () => {
  const { isScrolled, onScroll, scrollRef } = useScrollToTop();
  const { setContext } = useChatContext();
  const {
    data: docs,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
  } = useTRPCSuspenseInfiniteQuery((trpc) =>
    trpc.documents.getMany.infiniteQueryOptions(
      { cursor: 1 },
      { getNextPageParam: (lastPage) => lastPage.nextCursor },
    ),
  );

  useEffect(() => {
    if (docs != null) {
      const ctxt = docs.pages
        .flatMap((p) => p.posts)
        .map((p) => `DocumentId: ${p.id} Content:${p.text}`)
        .join("\n");
      setContext(ctxt);
    }
  }, [docs]);

  return (
    <>
      <DocumentScrollHeader
        count={docs.pages[0].totalDocs}
        scrollRef={scrollRef}
        isScrolled={isScrolled}
      />
      <ScrollableBox.ScrollArea
        ref={scrollRef}
        onScroll={onScroll}
        outerClassName="p-0!"
        className="bg-card min-h-full flex-1"
      >
        {docs.pages
          .flatMap((page) => page.posts)
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
