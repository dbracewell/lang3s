"use client";
import React, { Fragment, useMemo } from "react";
import {
  useTRPCInfiniteQuery,
  useTRPCSuspenseInfiniteQuery,
} from "@/lib/trpc/use-queries";
import { FileTextIcon } from "lucide-react";
import Link from "next/link";
import { formatURL } from "@/lib/utils/formatters";
import { InfiniteScroll } from "@/components/scrolling/InfiniteScroll";
import { SearchSpinner } from "@/features/search/ui/components/SearchSpinner";
import { ResultsWrapper } from "@/features/search/ui/components/ResultsWrapper";
import { DocumentHighlight } from "@/features/search/types";
import { useGlobalSearchParams } from "@/features/search/hooks/useSearchParams";

export const DocumentSearchView = () => {
  const [searchParams] = useGlobalSearchParams();
  const queryInput = useMemo(() => {
    const { tab, ...rest } = searchParams;
    return rest;
  }, [searchParams]);
  const {
    data: results,
    isLoading,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
  } = useTRPCSuspenseInfiniteQuery((trpc) =>
    trpc.search.searchDocuments.infiniteQueryOptions(
      { ...queryInput },
      {
        getNextPageParam: (lastPage) => lastPage?.nextCursor,
      },
    ),
  );

  if (isLoading || results == null) {
    return <SearchSpinner />;
  }

  return (
    <ResultsWrapper total={results.pages[0].total}>
      {results.pages
        .flatMap((page) => page.results)
        .map((r) => (
          <Fragment key={r.documentId}>
            <div className="flex w-full flex-col gap-1 px-2 py-3">
              <Link
                href={formatURL(`/documents/${r.documentId}`, {
                  ...searchParams,
                  cursor: 1,
                })}
                className="link flex items-center gap-2 text-lg"
              >
                <FileTextIcon className="size-4" /> {r.documentTitle}
              </Link>
              <div className="flex flex-col">
                {displayHighlights({
                  highlights: r.highlights,
                })}
              </div>
            </div>
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

const displayHighlights = ({
  highlights,
}: {
  highlights: DocumentHighlight[];
}) => {
  return (
    <>
      {highlights.slice(0, 5).map((highlight) => {
        return (
          <div
            key={highlight.text}
            className="contents whitespace-pre-line"
            dangerouslySetInnerHTML={{
              __html: `<p class='text-base whitespace-pre-line'>${highlight.text
                .replaceAll(
                  '<span class="keyword">',
                  "<b class='text-dodger-blue-500'>",
                )
                .replaceAll("</span>", "</b>")}</p>`,
            }}
          />
        );
      })}
      {highlights.length > 5 && (
        <p className="text-muted-foreground text-sm">
          ...and {highlights.length - 5} more
        </p>
      )}
    </>
  );
};
