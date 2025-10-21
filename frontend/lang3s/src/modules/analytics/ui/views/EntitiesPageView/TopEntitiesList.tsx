"use client";

import { Hint } from "@/components/hint";
import { Spinner } from "@/components/Spinner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useTagSearchParams } from "@/modules/analytics/hooks";
import { useDebounce } from "@/modules/common/hooks";
import { useTRPCQuery } from "@/trpc/use-queries";
import { ChartNetworkIcon, LoaderCircleIcon, SearchIcon } from "lucide-react";
import Link from "next/link";
import { parseAsString, useQueryState } from "nuqs";
import React, { useMemo, useState } from "react";

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
    <div className="mx-auto flex min-h-0 w-full max-w-5xl flex-1 flex-col gap-2">
      <Input
        placeholder="Filter by Entity..."
        className="max-w-md"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
      />
      <div className="flex flex-1 flex-col overflow-hidden rounded-lg border bg-white shadow">
        <div className="bg-dodger-blue-500 grid grid-cols-3 p-2 font-semibold text-white">
          <div className="text-center">Entity</div>
          <div className="text-center">Entity Type</div>
          <div className="text-center"># Occurrences</div>
        </div>
        <ScrollArea className="min-h-0 flex-1 pr-2">
          {filteredData?.map((r, index) => {
            return (
              <div
                key={index}
                className="hover:bg-dodger-blue-200 grid h-10 grid-cols-3 text-sm odd:bg-slate-200 hover:font-bold"
              >
                <div className="group flex items-center justify-between border-r px-4 py-1">
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
                <div className="my-auto border-r px-4 py-1">{r.value}</div>
                <div className="my-auto px-4 py-1">{r.count}</div>
              </div>
            );
          })}
        </ScrollArea>
      </div>
    </div>
  );
};
