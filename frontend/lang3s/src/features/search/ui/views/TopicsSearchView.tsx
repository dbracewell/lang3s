"use client";
import React, { Fragment } from "react";
import { InfiniteScroll } from "@/components/scrolling/InfiniteScroll";
import { SearchSpinner } from "@/features/search/ui/components/SearchSpinner";
import { ResultsWrapper } from "@/features/search/ui/components/ResultsWrapper";
import { formatCount } from "@/lib/utils/formatters";
import Link from "next/link";
import { FileIcon, MinusCircleIcon, PlusCircleIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useGlobalSearchParams } from "@/features/search/hooks/useSearchParams";
import { useInfiniteQuery } from "@tanstack/react-query";
import { searchTopicsInfiniteOptions } from "@/clients/core/@tanstack/react-query.gen";
import { coreClient } from "@/lib/api";

export const TopicSearchView = () => {
  const [searchParams, setSearchParams] = useGlobalSearchParams();
  const {
    data: results,
    isLoading,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
  } = useInfiniteQuery({
    ...searchTopicsInfiniteOptions({
      client: coreClient,
      body: {
        ...searchParams,
      },
    }),
    getNextPageParam: (lastPage) => lastPage?.next_cursor,
  });

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
              <div className="bg-background-lighter text-muted-foreground flex max-h-50 flex-col items-center gap-4 border-x px-5 pb-2 text-sm font-medium md:flex-row">
                <h3>
                  {formatCount(
                    new Set(r.highlights.map((h) => h.document_id)).size,
                    { single: "document", plural: "documents" },
                  )}
                </h3>
                <h3>
                  {formatCount(
                    new Set(r.highlights.map((h) => h.sentence_id)).size,
                    { single: "sentence", plural: "sentences" },
                  )}
                </h3>
              </div>
              <div className="bg-card flex flex-col gap-1 border p-1 px-2 text-sm">
                {r.highlights.map((h) => (
                  <div className="flex items-center gap-2" key={h.sentence_id}>
                    <Link
                      href={`/documents/${h.document_id}`}
                      className="link flex gap-1 first:pt-2 last:pb-2"
                    >
                      <FileIcon className="size-4" />
                    </Link>
                    <div
                      className="contents"
                      dangerouslySetInnerHTML={{
                        __html: `<p class='text-base'>${h.text
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
