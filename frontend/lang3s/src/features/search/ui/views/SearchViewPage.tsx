"use client";
import { Highlight } from "@/features/search/types";
import Link from "next/link";
import { ParsedSearchParams } from "@/features/search/params";
import { useTRPCInfiniteQuery } from "@/lib/trpc/use-queries";
import { InfiniteScroll } from "@/components/scrolling/InfiniteScroll";
import React, { Fragment, useRef, useState } from "react";
import { CircleQuestionMarkIcon, FileTextIcon, SearchIcon } from "lucide-react";
import { formatURL } from "@/lib/utils/formatters";
import { Hint } from "@/components/hint";
import { DocumentScrollHeader } from "@/components/scrolling/DocumentScrollHeader";

export const SearchViewPage = ({
  searchParams,
}: {
  searchParams: ParsedSearchParams;
}) => {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const [isScrolled, setIsScrolled] = useState(false);
  const {
    data: results,
    isLoading,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
  } = useTRPCInfiniteQuery((trpc) =>
    trpc.search.search.infiniteQueryOptions(
      { ...searchParams },
      { getNextPageParam: (lastPage) => lastPage.nextCursor, staleTime: 60 },
    ),
  );

  if (isLoading || results == null) {
    return (
      <div className="flex min-h-full flex-1 flex-col items-center justify-center">
        <SearchIcon className="text-dodger-blue-500 size-20 animate-pulse" />
        <span className="text-lg font-bold">Searching...</span>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-1 flex-col gap-3">
      <DocumentScrollHeader
        count={results.pages[0].total}
        scrollRef={scrollRef}
        isScrolled={isScrolled}
        isSearch={true}
      />
      <div className="flex min-h-0 flex-1 gap-2">
        <div
          className="scrollable bg-alternate-row/50 dark:bg-row/20 flex flex-1 flex-col rounded-lg border pr-2"
          ref={scrollRef}
          onScroll={(e) => {
            if (scrollRef.current) {
              const container = scrollRef.current;
              const scrollPosition =
                container.scrollTop + container.clientHeight;
              const scrollPercentage =
                (container.scrollHeight - scrollPosition) /
                container.scrollHeight;
              setIsScrolled(scrollPercentage < 0.8);
            }
          }}
        >
          {results.pages
            .flatMap((page) =>
              page.results.flatMap((r) => ({ type: page.type, ...r })),
            )
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
                      searchType: r.type,
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
        </div>
        <div className="hidden h-full min-h-0 w-[200px] overflow-clip rounded-lg border pb-12 md:block">
          <h1 className="bg-heading/70 flex items-center justify-center gap-2 border-b px-2 py-2 text-lg text-white dark:text-white">
            Top Entities{" "}
            <Hint hint="Number of documents this entity is mentioned in.">
              <CircleQuestionMarkIcon className="size-4" />
            </Hint>
          </h1>
          <div className="scrollable flex h-full flex-col gap-1">
            {results.pages[0].entities
              .filter((e) => e.count > 0.1 * results.pages[0].total)
              .map((e) => (
                <div
                  key={e.entity}
                  className="odd:bg-alternate-row/50 bg-row/50 grid w-full grid-cols-[3fr_1fr] gap-1 px-2 py-1 text-sm"
                >
                  <span>{e.entity}</span>
                  <span>
                    {new Intl.NumberFormat(undefined, {
                      style: "decimal",
                    }).format(e.count)}
                  </span>
                </div>
              ))}
          </div>
        </div>
      </div>
    </div>
  );
};

const displayHighlights = ({
  searchType,
  highlights,
}: {
  searchType: "annotation" | "sentence" | "document";
  highlights: Highlight[];
}) => {
  if (searchType === "annotation" || searchType === "sentence") {
    const counted: Record<string, number> = {};
    highlights.forEach((highlight) => {
      const h = formatHighlight(highlight);
      if (counted[h] == null) {
        counted[h] = 0;
      }
      counted[h]++;
    });
    return (
      <>
        {Object.entries(counted)
          .sort((a, b) => b[1] - a[1])
          .map(([key, value]) => (
            <div
              key={key}
              className="flex items-baseline justify-between gap-2"
            >
              {searchType === "annotation" && (
                <div className="w-full max-w-7 text-base! font-bold">
                  ({value})
                </div>
              )}
              <p
                className="flex-1 text-base"
                dangerouslySetInnerHTML={{
                  __html: key
                    .replaceAll('<span class="keyword">', "<b>")
                    .replaceAll("</span>", "</b>"),
                }}
              />
            </div>
          ))}
      </>
    );
  }
  return (
    <>
      {highlights.map((highlight, index) => {
        return (
          <p
            key={index}
            className="py-1 text-base"
            dangerouslySetInnerHTML={{
              __html: formatHighlight(highlight)
                .replaceAll('<span class="keyword">', "<b>")
                .replaceAll("</span>", "</b>"),
            }}
          />
        );
      })}
    </>
  );
};

const formatHighlight = (highlight: Highlight) => {
  if (highlight.a0 || highlight.a1 || highlight.time || highlight.location) {
    let response = `<span class="text-xs font-medium text-foreground">TRIGGER:</span><span class="text-base font-bold text-dodger-blue-500">${highlight.text.toUpperCase()}</span>`;
    if (highlight.a0 && highlight.a0.length > 0) {
      response += `&nbsp;&nbsp;&nbsp;<span class="text-xs font-medium  text-foreground">A0:</span><span class="text-base font-bold text-dodger-blue-500" >${highlight.a0.map((a) => a.toUpperCase()).join(", ")}</span>`;
    }
    if (highlight.a1 && highlight.a1.length > 0) {
      response += `&nbsp;&nbsp;&nbsp;<span class="text-xs font-medium  text-foreground">A1:</span><span class="text-base font-bold text-dodger-blue-500">${highlight.a1.map((a) => a.toUpperCase()).join(", ")}</span>`;
    }
    if (highlight.location) {
      response += `&nbsp;&nbsp;&nbsp;<span class="text-xs font-medium  text-foreground">LOC:</span><span class="text-base font-bold text-dodger-blue-500">${highlight.location.toUpperCase()}</span>`;
    }
    if (highlight.time) {
      response += `&nbsp;&nbsp;&nbsp;<span class="text-xs font-medium  text-foreground">TIME:</span><span class="text-base font-bold text-dodger-blue-500">${highlight.time.toUpperCase()}</span>`;
    }
    return response;
  }
  return highlight.text;
};
