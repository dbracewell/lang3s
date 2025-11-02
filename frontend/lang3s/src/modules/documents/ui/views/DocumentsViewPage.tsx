"use client";
import { InfiniteScroll } from "@/components/InfiniteScroll";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useTRPCSuspenseInfiniteQuery } from "@/trpc/use-queries";
import { ArrowUpIcon } from "lucide-react";
import Link from "next/link";
import { useRef, useState } from "react";

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
      { cursor: 0 },
      { getNextPageParam: (lastPage) => lastPage.nextCursor },
    ),
  );

  return (
    <div className="flex h-full flex-1 flex-col gap-3 overflow-hidden">
      <h1 className="mr-4 flex items-center justify-between rounded-lg border bg-zinc-100 p-2 text-lg">
        {docs.pages[0].totalDocs[0].count} Total Documents{" "}
        <Button
          className={cn(isScrolled ? "visible" : "hidden")}
          variant="secondary"
          onClick={() => {
            scrollRef.current?.scrollTo({
              top: 0,
            });
          }}
        >
          <ArrowUpIcon />
        </Button>
      </h1>
      <div
        ref={scrollRef}
        onScroll={(e) => {
          if (scrollRef.current) {
            const container = scrollRef.current;
            const scrollPosition = container.scrollTop + container.clientHeight;
            const scrollPercentage =
              (container.scrollHeight - scrollPosition) /
              container.scrollHeight;
            setIsScrolled(scrollPercentage < 0.8);
          }
        }}
        className="scrollable flex-1 pr-4"
      >
        {docs.pages
          .flatMap((page) => page.posts)
          .map((doc) => (
            <div
              key={doc.id}
              className="mb-3 flex flex-col overflow-clip rounded-lg border bg-white shadow"
            >
              <Link href={`/documents/${doc.id}`} className="link px-2 pt-2">
                {doc.title}
              </Link>
              <p className="p-2 text-sm">{doc.text}</p>
              <div className="border-t bg-zinc-50 p-2 pt-0">
                <h2 className="mt-2 text-sm font-semibold">Entities</h2>
                <div className="flex items-center gap-1 overflow-x-auto">
                  {doc.entities.slice(0, 5).map((e, i) => (
                    <div
                      key={i}
                      className="text-xs"
                      dangerouslySetInnerHTML={{
                        __html: (i > 0 ? " | " : "") + e,
                      }}
                    />
                  ))}
                </div>
              </div>
            </div>
          ))}
        <InfiniteScroll
          fetchNextPage={fetchNextPage}
          isFetchingNextPage={isFetchingNextPage}
          hasNextPage={hasNextPage}
        />
      </div>
    </div>
  );
};
