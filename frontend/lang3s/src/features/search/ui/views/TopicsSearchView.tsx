"use client";
import { useTRPCInfiniteQuery } from "@/lib/trpc/use-queries";
import React, { Fragment } from "react";
import { InfiniteScroll } from "@/components/scrolling/InfiniteScroll";
import { SearchSpinner } from "@/features/search/ui/components/SearchSpinner";
import { ResultsWrapper } from "@/features/search/ui/components/ResultsWrapper";
import { formatCount } from "@/lib/utils/formatters";
import Link from "next/link";
import { FileIcon, MinusCircleIcon, PlusCircleIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useGlobalSearchParams } from "@/features/search/hooks/useSearchParams";

export const TopicSearchView = () => {
  const [searchParams, setSearchParams] = useGlobalSearchParams();
  const {
    data: results,
    isLoading,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
  } = useTRPCInfiniteQuery((trpc) =>
    trpc.search.searchTopics.infiniteQueryOptions(
      { ...searchParams },
      {
        getNextPageParam: (lastPage) => lastPage?.nextCursor,
      },
    ),
  );

  if (searchParams.tab !== "topics") {
    return null;
  }

  if (isLoading || results == null) {
    return <SearchSpinner />;
  }

  return (
    <ResultsWrapper total={results.pages[0].total} header={"Topics"}>
      {results.pages
        .flatMap((page) => page.results)
        .map((r) => (
          <Fragment key={r.id}>
            <details className="group flex w-full flex-col px-2 py-1 first:pt-3">
              <summary className="bg-background-lighter cursor-pointer gap-2 border px-2 py-1 font-medium group-open:sticky group-open:top-0 group-open:border-b-0">
                <span className="mr-3">{r.name}</span>
                {!searchParams.tid.includes(r.id) ? (
                  <Button
                    variant="listButton"
                    className="h-fit!"
                    size="sm"
                    onClick={() => {
                      setSearchParams({
                        tid: [...searchParams.tid, r.id],
                      });
                    }}
                  >
                    <PlusCircleIcon className="size-3" /> Add to search
                  </Button>
                ) : (
                  <Button
                    variant="listButton"
                    className="h-fit!"
                    size="sm"
                    onClick={() => {
                      setSearchParams({
                        tid: searchParams.tid.filter((id) => id !== r.id),
                      });
                    }}
                  >
                    <MinusCircleIcon className="size-3" /> Remove from search
                  </Button>
                )}
              </summary>
              <div className="bg-background-lighter text-muted-foreground flex max-h-[200px] flex-col items-center gap-4 border-x px-5 pb-2 text-sm font-medium md:flex-row">
                <h3>
                  {formatCount(
                    new Set(r.highlights.map((h) => h.documentId)).size,
                    { single: "document", plural: "documents" },
                  )}
                </h3>
                <h3>
                  {formatCount(
                    new Set(r.highlights.map((h) => h.sentenceAid)).size,
                    { single: "sentence", plural: "sentences" },
                  )}
                </h3>
              </div>
              <div className="bg-card flex flex-col gap-1 border p-1 px-2 text-sm">
                {r.highlights.map((h) => (
                  <div className="flex items-center gap-2" key={h.sentenceAid}>
                    <Link
                      href={`/documents/${h.documentId}`}
                      className="link flex gap-1 first:pt-2 last:pb-2"
                    >
                      <FileIcon className="size-4" />
                    </Link>
                    <p
                      dangerouslySetInnerHTML={{
                        __html: `<p class='text-base'>${h.sentence
                          .replaceAll(
                            '<span class="keyword">',
                            "<b class='text-dodger-blue-500'>",
                          )
                          .replaceAll("</span>", "</b>")}</p>`,
                      }}
                    />
                  </div>
                ))}
              </div>
            </details>
          </Fragment>
        ))}
      <InfiniteScroll
        fetchNextPage={fetchNextPage}
        isFetchingNextPage={isFetchingNextPage}
        hasNextPage={hasNextPage}
      />
    </ResultsWrapper>
  );
};
