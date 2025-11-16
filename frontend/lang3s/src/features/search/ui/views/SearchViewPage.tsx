"use client";
import { cn } from "@/lib/utils";
import { SearchResults } from "@/features/search/types";
import Link from "next/link";

export const SearchViewPage = ({ results }: { results: SearchResults }) => {
  return (
    <div className="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-2 p-5">
      <div className="flex flex-1 flex-col gap-2">
        {results.results.map((r) => (
          <div className="flex items-start gap-2" key={r.documentId}>
            <div className="flex flex-col gap-1">
              <Link href={`/documents/${r.documentId}`} className="link">
                {r.documentTitle}
              </Link>
              <ul className="list-disc pl-5">
                {r.highlights.map((highlight, index) => (
                  <li key={index}>
                    {results.type === "vector" && (
                      <span className="mr-2 font-semibold">
                        {highlight.similarity.toFixed(2)}
                      </span>
                    )}
                    <span
                      dangerouslySetInnerHTML={{
                        __html: highlight.text
                          .replaceAll('<span class="keyword">', "<b>")
                          .replaceAll("</span>", "</b>"),
                      }}
                    />
                  </li>
                ))}
              </ul>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
