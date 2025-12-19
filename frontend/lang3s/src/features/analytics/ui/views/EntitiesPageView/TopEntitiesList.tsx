"use client";

import { Hint } from "@/components/hint";
import { Spinner } from "@/components/Spinner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useDebounce } from "@/hooks/useDebounce";
import { useTagSearchParams } from "@/features/analytics/hooks";
import { useTRPCQuery } from "@/lib/trpc/use-queries";
import {
  ChartNetworkIcon,
  CircleQuestionMarkIcon,
  SearchIcon,
  SquareActivityIcon,
} from "lucide-react";
import Link from "next/link";
import { parseAsString, useQueryState } from "nuqs";
import { useMemo, useState } from "react";
import { parseAsBoolean } from "nuqs/server";

export const TopEntitiesList = ({
  values,
  defaultValues,
}: {
  values: string[];
  defaultValues: string[];
}) => {
  const [filter, setFilter] = useState("");
  const [selectedValues] = useTagSearchParams(defaultValues);
  const [, setEntityText] = useQueryState(
    "entity",
    parseAsString.withDefault("").withOptions({ clearOnDefault: true }),
  );
  const [, setEntityType] = useQueryState(
    "entityType",
    parseAsString.withDefault("").withOptions({ clearOnDefault: true }),
  );
  const [, setShowEvents] = useQueryState(
    "showEvents",
    parseAsBoolean.withDefault(false).withOptions({ clearOnDefault: true }),
  );
  const debouncedFilter = useDebounce(filter, 500);

  const { data, isLoading } = useTRPCQuery((trpc) =>
    trpc.analytics.getAnnotationCounts.queryOptions({
      annotationType: "entity",
      values: selectedValues,
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
    <div className="mx-auto flex min-h-0 w-full flex-1 flex-col gap-2 p-3">
      <Input
        placeholder="Filter by Entity..."
        className="max-w-md"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
      />
      <div className="flex flex-1 flex-col overflow-hidden rounded-lg border bg-white shadow dark:bg-zinc-900">
        <div className="bg-heading grid grid-cols-5 p-2 font-semibold text-white">
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
                className="hover:bg-dodger-blue-200 dark:hover:bg-dodger-blue-800 even:bg-alternate-row bg-row grid h-10 grid-cols-5 divide-x text-sm hover:font-bold"
              >
                <div className="group flex items-center justify-between border-r px-4">
                  <div className="mr-4 truncate">{r.text}</div>
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
                    <Hint
                      asChild
                      hint={`Examine entities mentioned with ${r.text}.`}
                    >
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        className="hover:bg-dodger-blue-500 hover:text-white"
                        onClick={() => {
                          setEntityText(r.text);
                          setEntityType(r.value);
                        }}
                      >
                        <SquareActivityIcon />
                      </Button>
                    </Hint>
                    <Hint
                      asChild
                      hint={`Examine the events involving ${r.text}.`}
                    >
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        className="hover:bg-dodger-blue-500 hover:text-white"
                        onClick={() => {
                          setShowEvents(true);
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
