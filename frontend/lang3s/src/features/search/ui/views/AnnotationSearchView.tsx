"use client";
import { Lang3sSearchParams } from "@/features/search/params";
import { useTRPCInfiniteQuery } from "@/lib/trpc/use-queries";
import React, { Fragment } from "react";
import { InfiniteScroll } from "@/components/scrolling/InfiniteScroll";
import { useQueryStates } from "nuqs";
import { SearchSpinner } from "@/features/search/ui/components/SearchSpinner";
import { ResultsWrapper } from "@/features/search/ui/components/ResultsWrapper";
import { AnnotationSearchResult } from "@/features/search/types";
import { formatCount } from "@/lib/utils/formatters";
import Link from "next/link";
import { FileIcon, MinusCircleIcon, PlusCircleIcon } from "lucide-react";
import { Button } from "@/components/ui/button";

export const AnnotationSearchView = () => {
  const [searchParams] = useQueryStates(Lang3sSearchParams);
  const {
    data: results,
    isLoading,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
  } = useTRPCInfiniteQuery((trpc) =>
    trpc.search.searchAnnotations.infiniteQueryOptions(
      { ...searchParams },
      {
        getNextPageParam: (lastPage) => lastPage?.nextCursor,
      },
    ),
  );

  if (searchParams.tab !== "annotations") {
    return null;
  }

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
              <div className="bg-row flex max-h-[200px] flex-col gap-1 border-x px-5 text-sm font-semibold dark:bg-zinc-900">
                {formatCount(
                  new Set(r.highlights.map((h) => h.documentId)).size,
                  { single: "document", plural: "documents" },
                )}
              </div>
              <div className="bg-card flex flex-col gap-1 border p-1 px-2 text-sm">
                {[...new Set(r.highlights.map((h) => h.documentTitle))].map(
                  (h) => (
                    <Link
                      key={h}
                      href={`/documents/${h}`}
                      className="link flex gap-1 first:pt-2 last:pb-2"
                    >
                      <FileIcon className="size-4" /> {h}
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

const hasAll = (big: string[], small: string[]) => {
  const s1 = new Set(big);
  const s2 = new Set(small);
  console.log(s1.size, s2.size, s2.difference(s1).size, s1.union(s2).size);
  return s2.difference(s1).size === 0;
};

const AnnotationFormat = ({ result }: { result: AnnotationSearchResult }) => {
  const isEventive = result.a0 || result.a1 || result.time || result.location;
  const [searchParams, setSearchParams] = useQueryStates(Lang3sSearchParams);
  if (isEventive) {
    return (
      <summary className="bg-row gap-2 border px-2 py-1 group-group-open:top-0 group-open:sticky group-open:border-b-0 dark:bg-zinc-900">
        <span className="font-medium">
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
        </span>
      </summary>
    );
  }

  return (
    <summary className="bg-row cursor-pointer border border-b px-2 py-1 font-medium group-open:sticky group-open:top-0 group-open:border-b-0 dark:bg-zinc-900">
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
