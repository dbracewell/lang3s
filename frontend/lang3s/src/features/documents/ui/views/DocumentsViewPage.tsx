"use client";
import { InfiniteScroll } from "@/components/scrolling/InfiniteScroll";
import { useTRPCSuspenseInfiniteQuery } from "@/lib/trpc/use-queries";
import Link from "next/link";
import { useRef, useState } from "react";
import { DocumentScrollHeader } from "@/components/scrolling/DocumentScrollHeader";
import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import { DocumentResult } from "@/features/documents/ui/components/DocumentResult";
import { formatNumber } from "@/lib/utils/formatters";
import { Skeleton } from "@/components/ui/skeleton";

export const DocumentsViewPage = () => {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const [isScrolled, setIsScrolled] = useState(false);

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

  return (
    <>
      <DocumentScrollHeader
        count={docs.pages[0].totalDocs[0].count}
        scrollRef={scrollRef}
        isScrolled={isScrolled}
      />
      <ScrollableBox.ScrollArea
        ref={scrollRef}
        onScroll={() => {
          if (scrollRef.current) {
            const container = scrollRef.current;
            const scrollPosition = container.scrollTop + container.clientHeight;
            const scrollPercentage =
              (container.scrollHeight - scrollPosition) /
              container.scrollHeight;
            setIsScrolled(scrollPercentage < 0.8);
          }
        }}
        outerClassName="p-0!"
        className="bg-alternate-row/50 dark:bg-row/20 min-h-full flex-1"
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
