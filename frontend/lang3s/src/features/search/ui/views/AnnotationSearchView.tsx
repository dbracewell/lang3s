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
import { searchAnnotationsInfiniteOptions } from "@/clients/core/@tanstack/react-query.gen";
import { coreClient } from "@/lib/api";
import { AnnotationSearchResult } from "@/clients/core";

export const AnnotationSearchView = () => {
  const [searchParams] = useGlobalSearchParams();
  const {
    data: results,
    isLoading,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
  } = useInfiniteQuery({
    ...searchAnnotationsInfiniteOptions({
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
              <div className="bg-row dark:bg-background-lighter flex max-h-50 gap-3 border-x px-5 text-sm font-semibold">
                <span>
                  {formatCount(r.docs.length, {
                    single: "document",
                    plural: "documents",
                  })}
                </span>
                <span>
                  {formatCount(
                    r.docs.flatMap((d) => d.highlights.length).length,
                    {
                      single: "mention",
                      plural: "mentions",
                    },
                  )}
                </span>
              </div>
              <div className="bg-card flex flex-col gap-1 border p-1 px-2 text-sm">
                {r.docs.map((h) => (
                  <div key={h.document_id} className="flex flex-col gap-1">
                    <Link
                      key={h.document_id}
                      href={`/documents/${h.document_id}`}
                      className="link flex gap-1 first:pt-2 last:pb-2"
                    >
                      <FileIcon className="size-4" /> {h.document_title}
                    </Link>
                    {h.highlights.map((highlight) => (
                      <div key={highlight.sentence_id}>
                        <span
                          dangerouslySetInnerHTML={{
                            __html: highlight.annotation.replaceAll(
                              '<span class="keyword">',
                              "<b class='text-dodger-blue-500'>",
                            ),
                          }}
                        />
                        : {highlight.sentence}
                      </div>
                    ))}
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

const AnnotationFormat = ({ result }: { result: AnnotationSearchResult }) => {
  // const isEventive = result.a0 || result.a1 || result.time || result.location;
  const [searchParams, setSearchParams] = useGlobalSearchParams();
  // if (isEventive) {
  //   const searchTextParts: string[] = [
  //     `"${result.text.replaceAll(/<[^>]+>/g, "")}"`,
  //   ];
  //   result.a0?.forEach((a) => searchTextParts.push(`"${a}"`));
  //   result.a1?.forEach((a) => searchTextParts.push(`"${a}"`));
  //   if (result.time) {
  //     searchTextParts.push(`"${result.time}"`);
  //   }
  //   if (result.location) {
  //     searchTextParts.push(`"${result.location}"`);
  //   }
  //   const searchText = searchTextParts.join(" OR ");
  //
  //   return (
  //     <summary className="bg-row dark:bg-background-lighter gap-2 border px-2 py-1 group-group-open:top-0 group-open:sticky group-open:border-b-0">
  //       <span className="font-medium">
  //         <div
  //           className="contents"
  //           dangerouslySetInnerHTML={{
  //             __html: `${result.name
  //               .replaceAll(
  //                 '<span class="keyword">',
  //                 "<b class='text-dodger-blue-500'>",
  //               )
  //               .replaceAll("</span>", "</b>")}`,
  //           }}
  //         />
  //         <span className="text-muted-foreground ml-1">
  //           {result.path.split(".").slice(-1)[0]}
  //         </span>
  {
    /*{result.a0 && result.a0.length > 0 && (*/
  }
  {
    /*  <span className="ml-2">*/
  }
  {
    /*    <span>A0:</span>*/
  }
  {
    /*    {result.a0.map((value, i) => (*/
  }
  {
    /*      <span key={value} className="ml-1 font-normal">*/
  }
  {
    /*        {i > 0 ? ", " : ""}*/
  }
  {
    /*        {value.toUpperCase()}*/
  }
  {
    /*      </span>*/
  }
  {
    /*    ))}*/
  }
  {
    /*  </span>*/
  }
  {
    /*)}*/
  }
  {
    /*{result.a1 && result.a1.length > 0 && (*/
  }
  {
    /*  <span className="ml-2">*/
  }
  {
    /*    <span>A1:</span>*/
  }
  {
    /*    {result.a1.map((value, i) => (*/
  }
  {
    /*      <span key={value} className="ml-1 font-normal">*/
  }
  {
    /*        {i > 0 ? ", " : ""}*/
  }
  {
    /*        {value}*/
  }
  {
    /*      </span>*/
  }
  {
    /*    ))}*/
  }
  {
    /*  </span>*/
  }
  {
    /*)}*/
  }
  {
    /*{result.location && (*/
  }
  {
    /*  <span className="ml-2">*/
  }
  {
    /*    <span>Location:</span>*/
  }
  {
    /*    <span className="ml-1 font-normal">{result.location}</span>*/
  }
  {
    /*  </span>*/
  }
  {
    /*)}*/
  }
  {
    /*{result.time && (*/
  }
  {
    /*  <span className="ml-2">*/
  }
  {
    /*    <span>Time:</span>*/
  }
  {
    /*    <span className="ml-1 font-normal">{result.time}</span>*/
  }
  {
    /*  </span>*/
  }
  {
    /*)}*/
  }
  //
  //         {!searchParams.q.includes(searchText) ? (
  //           <Button
  //             variant="listButton"
  //             className="ml-3 h-fit!"
  //             size="sm"
  //             onClick={() => {
  //               setSearchParams({
  //                 q: !!searchParams.q
  //                   ? `${searchParams.q} OR ${searchText}`
  //                   : searchText,
  //               });
  //             }}
  //           >
  //             <PlusCircleIcon className="size-3" /> Add to search
  //           </Button>
  //         ) : (
  //           <Button
  //             variant="listButton"
  //             className="ml-3 h-fit!"
  //             size="sm"
  //             onClick={() => {
  //               const firstR = new RegExp(
  //                 `^${searchText} OR|OR ${searchText}$|OR ${searchText}|${searchText}`,
  //               );
  //               setSearchParams({
  //                 q: searchParams.q.replace(firstR, "").trim(),
  //               });
  //             }}
  //           >
  //             <MinusCircleIcon className="size-3" /> Remove from search
  //           </Button>
  //         )}
  //       </span>
  //     </summary>
  //   );
  // }

  return (
    <summary className="bg-row dark:bg-background-lighter cursor-pointer border border-b px-2 py-1 font-medium group-open:sticky group-open:top-0 group-open:border-b-0">
      <span
        dangerouslySetInnerHTML={{
          __html: `${result.name
            .replaceAll(
              '<span class="keyword">',
              "<b class='text-dodger-blue-500'>",
            )
            .replaceAll("</span>", "</b>")}`,
        }}
      />
      <span className="text-muted-foreground mr-3 ml-1">
        {result.path.split(".").slice(-1)[0]}
      </span>
      {!searchParams.q.includes(
        `"${result.name.replaceAll(/<[^>]+>/g, "")}"`,
      ) ? (
        <Button
          variant="listButton"
          className="h-fit!"
          size="sm"
          onClick={() => {
            setSearchParams({
              q: !!searchParams.q
                ? `${searchParams.q} OR "${result.name.replaceAll(/<[^>]+>/g, "")}"`
                : `"${result.name.replaceAll(/<[^>]+>/g, "")}"`,
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
                .replace(`OR "${result.name.replaceAll(/<[^>]+>/g, "")}"`, "")
                .replace(`"${result.name.replaceAll(/<[^>]+>/g, "")}"`, "")
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
