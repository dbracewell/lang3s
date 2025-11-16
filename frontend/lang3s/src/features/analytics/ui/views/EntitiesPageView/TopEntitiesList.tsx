"use client";

import { Hint } from "@/components/hint";
import { Spinner } from "@/components/Spinner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useDebounce } from "@/hooks/useDebounce";
import { useTagSearchParams } from "@/features/analytics/hooks";
import { useTRPCQuery } from "@/trpc/use-queries";
import {
  ChartNetworkIcon,
  CircleQuestionMarkIcon,
  SearchIcon,
} from "lucide-react";
import Link from "next/link";
import { parseAsString, useQueryState } from "nuqs";
import { useMemo, useState } from "react";

export const TopEntitiesList = ({ values }: { values: string[] }) => {
  const [filter, setFilter] = useState("");
  const [selectedValues] = useTagSearchParams(values);
  const [, setEntityText] = useQueryState(
    "entity",
    parseAsString.withDefault("").withOptions({ clearOnDefault: true }),
  );
  const [, setEntityType] = useQueryState(
    "entityType",
    parseAsString.withDefault("").withOptions({ clearOnDefault: true }),
  );
  const debouncedSelectedValues = useDebounce(selectedValues, 1000);
  const debouncedFilter = useDebounce(filter, 100);

  const { data, isLoading } = useTRPCQuery((trpc) =>
    trpc.analytics.getAnnotationCounts.queryOptions({
      annotationType: "entity",
      values: debouncedSelectedValues,
    }),
  );

  const filteredData = useMemo(() => {
    const filterText = debouncedFilter.trim().toUpperCase();
    if (!!filterText) {
      return data?.filter((r) => r.text.includes(filterText));
    }
    return data;
  }, [data, debouncedFilter]);

  if (isLoading) {
    return <Spinner />;
  }

  return (
    <div className="mx-auto flex min-h-0 w-full flex-1 flex-col gap-2">
      <Input
        placeholder="Filter by Entity..."
        className="max-w-md"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
      />
      <div className="flex flex-1 flex-col overflow-hidden rounded-lg border bg-white shadow">
        <div className="bg-dodger-blue-500 grid grid-cols-5 p-2 font-semibold text-white">
          <div className="text-center">Entity</div>
          <div className="text-center">Entity Type</div>
          <div className="flex items-center justify-center gap-1">
            Mention Count
            <Hint
              hint={`Number of times this entity is mentioned\n(Includes multiple mentions per document.)`}
            >
              <CircleQuestionMarkIcon className="size-4" />
            </Hint>
          </div>
          <div className="flex items-center justify-center gap-1">
            Document Count
            <Hint hint="Number of documents in which this entity appears">
              <CircleQuestionMarkIcon className="size-4" />
            </Hint>
          </div>
          <div className="flex items-center justify-center gap-1">
            Mentions Per Document
            <Hint hint="Average number of times the entity is mentioned in documents in which it appears.">
              <CircleQuestionMarkIcon className="size-4" />
            </Hint>
          </div>
        </div>
        <div className="scrollable flex-1">
          {filteredData?.map((r, index) => {
            return (
              <div
                key={index}
                className="hover:bg-dodger-blue-200 grid h-10 grid-cols-5 divide-x text-sm odd:bg-slate-200 hover:font-bold"
              >
                <div className="group flex items-center justify-between border-r px-4">
                  <div className="mr-4">{r.text}</div>
                  <div className="hidden items-center gap-2 group-hover:flex">
                    <Hint asChild hint={`Search for ${r.text} in documents.`}>
                      <Button
                        asChild
                        variant="ghost"
                        size="icon-sm"
                        className="hover:bg-dodger-blue-500 hover:text-white"
                      >
                        <Link href={`/search?q=${encodeURIComponent(r.text)}`}>
                          <SearchIcon />
                        </Link>
                      </Button>
                    </Hint>
                    <Hint asChild hint="Examine co-occurring entities.">
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        className="hover:bg-dodger-blue-500 hover:text-white"
                        onClick={() => {
                          setEntityText(r.text);
                          setEntityType(r.value);
                        }}
                      >
                        <ChartNetworkIcon />
                      </Button>
                    </Hint>
                  </div>
                </div>
                <div className="flex items-center px-4">{r.value}</div>
                <div className="flex items-center px-4">{r.count}</div>
                <div className="flex items-center px-4">{r.docCount}</div>
                <div className="flex items-center px-4">
                  {r.mentionsPerDocument}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
