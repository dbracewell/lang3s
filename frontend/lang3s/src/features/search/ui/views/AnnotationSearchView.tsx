"use client";
import {
  useTRPCInfiniteQuery,
  useTRPCSuspenseInfiniteQuery,
} from "@/lib/trpc/use-queries";
import React, { Fragment, useMemo } from "react";
import { InfiniteScroll } from "@/components/scrolling/InfiniteScroll";
import { SearchSpinner } from "@/features/search/ui/components/SearchSpinner";
import { ResultsWrapper } from "@/features/search/ui/components/ResultsWrapper";
import { AnnotationSearchResult } from "@/features/search/types";
import { formatCount } from "@/lib/utils/formatters";
import Link from "next/link";
import { FileIcon, MinusCircleIcon, PlusCircleIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useGlobalSearchParams } from "@/features/search/hooks/useSearchParams";

export const AnnotationSearchView = () => {
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
    trpc.search.searchAnnotations.infiniteQueryOptions(
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
    <ResultsWrapper
      total={results.pages[0].total}
      header={"Unique Annotations"}
    >
      {results.pages
        .flatMap((page) => page.results)
        .map((r) => (
          <Fragment key={JSON.stringify(r)}>
            <details className="group flex w-full flex-col px-2 py-1 first:pt-3">
              <AnnotationFormat result={r} />
              <div className="bg-row dark:bg-background-lighter flex max-h-[200px] flex-col gap-1 border-x px-5 text-sm font-semibold">
                {formatCount(
                  new Set(r.highlights.map((h) => h.documentId)).size,
                  { single: "document", plural: "documents" },
                )}
              </div>
              <div className="bg-card flex flex-col gap-1 border p-1 px-2 text-sm">
                {[...new Set(r.highlights.map((h) => h.documentId))].map(
                  (h) => (
                    <Link
                      key={h}
                      href={`/documents/${h}`}
                      className="link flex gap-1 first:pt-2 last:pb-2"
                    >
                      <FileIcon className="size-4" />{" "}
                      {
                        r.highlights.find((t) => t.documentId === h)
                          ?.documentTitle
                      }
                    </Link>
                  ),
                )}
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

const AnnotationFormat = ({ result }: { result: AnnotationSearchResult }) => {
  const isEventive = result.a0 || result.a1 || result.time || result.location;
  const [searchParams, setSearchParams] = useGlobalSearchParams();
  if (isEventive) {
    const searchTextParts: string[] = [
      `"${result.text.replaceAll(/<[^>]+>/g, "")}"`,
    ];
    result.a0?.forEach((a) => searchTextParts.push(`"${a}"`));
    result.a1?.forEach((a) => searchTextParts.push(`"${a}"`));
    if (result.time) {
      searchTextParts.push(`"${result.time}"`);
    }
    if (result.location) {
      searchTextParts.push(`"${result.location}"`);
    }
    const searchText = searchTextParts.join(" OR ");

    return (
      <summary className="bg-row dark:bg-background-lighter gap-2 border px-2 py-1 group-group-open:top-0 group-open:sticky group-open:border-b-0">
        <span className="font-medium">
          <div
            className="contents"
            dangerouslySetInnerHTML={{
              __html: `${result.text
                .replaceAll(
                  '<span class="keyword">',
                  "<b class='text-dodger-blue-500'>",
                )
                .replaceAll("</span>", "</b>")}`,
            }}
          />
          <span className="text-muted-foreground ml-1">
            {result.value.split(".").slice(-1)[0]}
          </span>
          {result.a0 && result.a0.length > 0 && (
            <span className="ml-2">
              <span>A0:</span>
              {result.a0.map((value, i) => (
                <span key={value} className="ml-1 font-normal">
                  {i > 0 ? ", " : ""}
                  {value.toUpperCase()}
                </span>
              ))}
            </span>
          )}
          {result.a1 && result.a1.length > 0 && (
            <span className="ml-2">
              <span>A1:</span>
              {result.a1.map((value, i) => (
                <span key={value} className="ml-1 font-normal">
                  {i > 0 ? ", " : ""}
                  {value}
                </span>
              ))}
            </span>
          )}
          {result.location && (
            <span className="ml-2">
              <span>Location:</span>
              <span className="ml-1 font-normal">{result.location}</span>
            </span>
          )}
          {result.time && (
            <span className="ml-2">
              <span>Time:</span>
              <span className="ml-1 font-normal">{result.time}</span>
            </span>
          )}

          {!searchParams.q.includes(searchText) ? (
            <Button
              variant="listButton"
              className="ml-3 h-fit!"
              size="sm"
              onClick={() => {
                setSearchParams({
                  q: !!searchParams.q
                    ? `${searchParams.q} OR ${searchText}`
                    : searchText,
                });
              }}
            >
              <PlusCircleIcon className="size-3" /> Add to search
            </Button>
          ) : (
            <Button
              variant="listButton"
              className="ml-3 h-fit!"
              size="sm"
              onClick={() => {
                const firstR = new RegExp(
                  `^${searchText} OR|OR ${searchText}$|OR ${searchText}|${searchText}`,
                );
                setSearchParams({
                  q: searchParams.q.replace(firstR, "").trim(),
                });
              }}
            >
              <MinusCircleIcon className="size-3" /> Remove from search
            </Button>
          )}
        </span>
      </summary>
    );
  }

  return (
    <summary className="bg-row dark:bg-background-lighter cursor-pointer border border-b px-2 py-1 font-medium group-open:sticky group-open:top-0 group-open:border-b-0">
      <span
        dangerouslySetInnerHTML={{
          __html: `${result.text
            .replaceAll(
              '<span class="keyword">',
              "<b class='text-dodger-blue-500'>",
            )
            .replaceAll("</span>", "</b>")}`,
        }}
      />
      <span className="text-muted-foreground mr-3 ml-1">
        {result.value.split(".").slice(-1)[0]}
      </span>
      {!searchParams.q.includes(
        `"${result.text.replaceAll(/<[^>]+>/g, "")}"`,
      ) ? (
        <Button
          variant="listButton"
          className="h-fit!"
          size="sm"
          onClick={() => {
            setSearchParams({
              q: !!searchParams.q
                ? `${searchParams.q} OR "${result.text.replaceAll(/<[^>]+>/g, "")}"`
                : `"${result.text.replaceAll(/<[^>]+>/g, "")}"`,
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
              q: searchParams.q
                .replace(`OR "${result.text.replaceAll(/<[^>]+>/g, "")}"`, "")
                .replace(`"${result.text.replaceAll(/<[^>]+>/g, "")}"`, "")
                .trim(),
            });
          }}
        >
          <MinusCircleIcon className="size-3" /> Remove from search
        </Button>
      )}
    </summary>
  );
};
