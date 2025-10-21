"use client";
import { type RouterOutputs } from "@/trpc/types";
import Link from "next/link";

export const SearchViewPage = ({
  results,
}: {
  results: RouterOutputs["search"]["search"];
}) => {
  return (
    <div className="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-2 p-5">
      <div className="flex flex-1 flex-col gap-2">
        {results.map((r) => (
          <div className="flex items-start gap-2" key={r.documentId}>
            <div>{Number(r.rank).toFixed(2)}</div>
            <div className="flex flex-col gap-1">
              <Link href={`/documents/${r.documentId}`} className="link">
                {r.title}
              </Link>
              <div
                className="whitespace-pre-line"
                dangerouslySetInnerHTML={{
                  __html: r.highlight
                    .replaceAll('<span class="keyword">', "<b>")
                    .replaceAll("</span>", "</b>"),
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
