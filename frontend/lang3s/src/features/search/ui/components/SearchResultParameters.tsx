"use client";
import { useQueryStates } from "nuqs";
import { Lang3sSearchParams } from "@/features/search/params";
import { useTRPCQuery } from "@/lib/trpc/use-queries";

export const SearchResultParameters = () => {
  const [searchParams] = useQueryStates(Lang3sSearchParams);
  const { data, isPending } = useTRPCQuery((trpc) =>
    trpc.search.searchParameters.queryOptions({
      q: searchParams.q,
      tid: searchParams.tid,
      aid: searchParams.aid,
      sid: searchParams.sid,
      isStrict: searchParams.isStrict,
    }),
  );
  if (isPending || data == null) {
    return null;
  }
  return (
    <details className="pageSubheading flex flex-col gap-0.5">
      <summary className="cursor-pointer px-2 py-1">Search Details</summary>
      <div className="flex flex-wrap gap-3 p-1 text-xs">
        <div className="flex flex-col gap-1">
          <div>
            <span className="font-semibold"> Strict:</span>{" "}
            {String(data.isStrict)}
          </div>
          {data.query && (
            <div className="flex items-center gap-1">
              <span className="font-semibold"> Query:</span> {data.query}
            </div>
          )}
        </div>
        {data.topics.length > 0 && (
          <div className="flex flex-col gap-1">
            <h2 className="font-semibold">Topics</h2>
            {data.topics.map((topic) => (
              <div key={topic.id}>{topic.name}</div>
            ))}
          </div>
        )}
        {data.annotations.length > 0 && (
          <div className="flex flex-col gap-1">
            <h2 className="font-semibold">Annotations</h2>
            {[
              ...new Set(
                data.annotations.map((annotation) => annotation.content),
              ),
            ].map((annotation) => (
              <div key={annotation}>{annotation}</div>
            ))}
          </div>
        )}
        {data.sentences.length > 0 && (
          <div className="flex flex-col gap-1">
            <h2 className="font-semibold">Sentences</h2>
            {data.sentences.map((annotation) => (
              <div key={annotation.id}>{annotation.content}</div>
            ))}
          </div>
        )}
      </div>
    </details>
  );
};
