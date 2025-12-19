"use client";
import { InfiniteScroll } from "@/components/InfiniteScroll";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils/cn";
import { useTRPCSuspenseInfiniteQuery } from "@/lib/trpc/use-queries";
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
      { cursor: 1 },
      { getNextPageParam: (lastPage) => lastPage.nextCursor },
    ),
  );

  return (
    <div className="flex h-full flex-1 flex-col gap-3">
      <div className="bg-heading flex h-10 items-center justify-between rounded-lg border p-2 text-lg font-bold text-white">
        {new Intl.NumberFormat(undefined, {
          style: "decimal",
        }).format(docs.pages[0].totalDocs[0].count)}{" "}
        Total Documents{" "}
        <Button
          className={cn(
            "hover:bg-white/50! dark:hover:bg-white/30!",
            isScrolled ? "visible" : "hidden",
          )}
          variant="ghost"
          size="icon-xs"
          onClick={() => {
            scrollRef.current?.scrollTo({
              top: 0,
            });
          }}
        >
          <ArrowUpIcon />
        </Button>
      </div>
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
        className="scrollable flex flex-1 flex-col gap-2 pr-2"
      >
        {docs.pages
          .flatMap((page) => page.posts)
          .map((doc, index) => (
            <div
              key={doc.id}
              className={cn(
                "bg-row mb-3 flex flex-col overflow-clip rounded-lg border",
                index % 2 == 1 && "bg-alternate-row",
              )}
            >
              <Link href={`/documents/${doc.id}`} className="link mt-2 px-2">
                {doc.title}
              </Link>
              <p className="p-2 text-sm">{doc.text}</p>
              <div
                className={cn(
                  "border-t bg-slate-300 p-2 pt-2 dark:bg-gray-800",
                  index % 2 == 1 && "bg-slate-300! dark:bg-gray-800!",
                )}
              >
                <h2 className="text-sm font-semibold">Entities</h2>
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
