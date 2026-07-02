"use client";
import { useGlobalSearchParams } from "@/features/search/hooks/useSearchParams";
import { useQuery } from "@tanstack/react-query";
import { searchHumanizeOptions } from "@/clients/core/@tanstack/react-query.gen";
import { coreClient } from "@/lib/api";

export const SearchResultParameters = () => {
  const [searchParams] = useGlobalSearchParams();
  const { data } = useQuery({
    ...searchHumanizeOptions({
      client: coreClient,
      body: {
        ...searchParams,
      },
    }),
  });
  return (
    <details className="pageSubheading flex flex-col gap-0.5">
      <summary className="cursor-pointer px-2 py-1">Search Details</summary>
      <div className="flex flex-wrap gap-3 p-1 text-xs">
        <div className="flex flex-col gap-1">
          <div>
            <span className="font-semibold"> Strict:</span>{" "}
            {String(searchParams.is_strict)}
          </div>
          {searchParams.q && (
            <div className="flex items-center gap-1">
              <span className="font-semibold"> Query:</span> {searchParams.q}
            </div>
          )}
        </div>
        {data?.topics && data.topics.length > 0 && (
          <div className="flex flex-col gap-1">
            <h2 className="font-semibold">Topics</h2>
            {data.topics.map((topic) => (
              <div key={topic}>{topic}</div>
            ))}
          </div>
        )}
        {data?.annotations && data.annotations.length > 0 && (
          <div className="flex flex-col gap-1">
            <h2 className="font-semibold">Annotations</h2>
            {[...new Set(data.annotations.map((annotation) => annotation))].map(
              (annotation) => (
                <div key={annotation}>{annotation}</div>
              ),
            )}
          </div>
        )}
        {/*{data.sentences.length > 0 && (*/}
        {/*  <div className="flex flex-col gap-1">*/}
        {/*    <h2 className="font-semibold">Sentences</h2>*/}
        {/*    {data.sentences.map((annotation) => (*/}
        {/*      <div key={annotation.id}>{annotation.content}</div>*/}
        {/*    ))}*/}
        {/*  </div>*/}
        {/*)}*/}
      </div>
    </details>
  );
};
