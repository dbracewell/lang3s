"use client";

import { Hint } from "@/components/hint";
import { Spinner } from "@/components/Spinner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useTRPCQuery } from "@/lib/trpc/use-queries";
import {
  ArrowDownIcon,
  ChartNetworkIcon,
  CircleQuestionMarkIcon,
  SearchIcon,
  SquareActivityIcon,
} from "lucide-react";
import Link from "next/link";
import { parseAsString, useQueryState } from "nuqs";
import { useEffect, useState } from "react";
import { parseAsBoolean } from "nuqs/server";
import { formatNumber, formatURL } from "@/lib/utils/formatters";
import { PageNumbers } from "@/components/PageNumbers";
import { useRouter } from "next/navigation";
import { defaultValues } from "@/features/analytics/ui/views/EntitiesPageView/index";

export const TopEntitiesList = ({
  values,
  sortBy,
  page,
  filter,
}: {
  page: number;
  sortBy: string;
  filter?: string;
  values: string[];
}) => {
  const [newFilter, setNewFilter] = useState(filter);
  let finalSortBy = sortBy.toLowerCase();
  if (!["mentions", "docs", "mentionsperdoc"].includes(sortBy.toLowerCase())) {
    finalSortBy = "mentions";
  }
  const router = useRouter();
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

  useEffect(() => {
    setNewFilter(filter);
  }, [filter]);

  const { data, isLoading } = useTRPCQuery((trpc) =>
    trpc.analytics.getAnnotationCounts.queryOptions({
      annotationType: "entity",
      values,
      page,
      sortBy: finalSortBy,
      filter,
    }),
  );

  if (isLoading || data == null) {
    return <Spinner />;
  }

  return (
    <div className="mx-auto flex min-h-0 w-full flex-1 flex-col gap-2 p-3">
      <div className="flex items-center gap-5">
        <Input
          placeholder="Filter by Entity (Press enter to search)..."
          className="max-w-md"
          value={newFilter ?? ""}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              router.push(
                formatURL("/analytics/entities", {
                  filter: newFilter,
                  sortBy: sortBy === "mentions" ? undefined : sortBy,
                  tags:
                    new Set(values).union(new Set(defaultValues)).size ==
                    defaultValues.length
                      ? undefined
                      : values.join(","),
                }),
              );
            }
          }}
          onChange={(e) => setNewFilter(e.target.value)}
        />
        <div className="hidden flex-1 text-lg font-semibold md:block">
          {formatNumber(data.total)} total Entities
        </div>
      </div>
      <div className="flex flex-1 flex-col overflow-hidden rounded-lg border bg-white shadow dark:bg-zinc-900">
        <div className="bg-heading grid grid-cols-5 p-2 font-semibold text-white">
          <div className="text-center">Entity</div>
          <div className="text-center">Entity Type</div>
          <div className="flex items-center justify-center gap-2">
            {finalSortBy === "mentions" ? (
              <span className="flex items-center">
                <ArrowDownIcon className="mr-2 size-4" /> Mention Count
              </span>
            ) : (
              <Link
                href={formatURL("/analytics/entities", {
                  filter: newFilter,
                  sortBy: "mentions",
                  tags:
                    new Set(values).union(new Set(defaultValues)).size ==
                    defaultValues.length
                      ? undefined
                      : values.join(","),
                })}
              >
                Mention Count{" "}
              </Link>
            )}
            <Hint
              hint={`Number of times this entity is mentioned\n(Includes multiple mentions per document.)`}
            >
              <CircleQuestionMarkIcon className="size-4" />
            </Hint>
          </div>
          <div className="flex items-center justify-center gap-2">
            {finalSortBy === "docs" ? (
              <span className="flex items-center">
                <ArrowDownIcon className="mr-2 size-4" /> Document Count
              </span>
            ) : (
              <Link
                href={formatURL("/analytics/entities", {
                  filter: newFilter,
                  sortBy: "docs",
                  tags:
                    new Set(values).union(new Set(defaultValues)).size ==
                    defaultValues.length
                      ? undefined
                      : values.join(","),
                })}
                className="hover:underline"
              >
                Document Count{" "}
              </Link>
            )}
            <Hint hint="Number of documents in which this entity appears">
              <CircleQuestionMarkIcon className="size-4" />
            </Hint>
          </div>
          <div className="flex items-center justify-center gap-1">
            {finalSortBy === "mentionsperdoc" ? (
              <span className="flex items-center">
                <ArrowDownIcon className="mr-2 size-4" /> Mentions Per Document
              </span>
            ) : (
              <Link
                href={formatURL("/analytics/entities", {
                  filter: newFilter,
                  sortBy: "mentionsPerDoc",
                  tags:
                    new Set(values).union(new Set(defaultValues)).size ==
                    defaultValues.length
                      ? undefined
                      : values.join(","),
                })}
                className="hover:underline"
              >
                Mentions Per Document
              </Link>
            )}
            <Hint hint="Average number of times the entity is mentioned in documents in which it appears.">
              <CircleQuestionMarkIcon className="size-4" />
            </Hint>
          </div>
        </div>
        <div className="scrollable flex-1">
          {data.results.map((r, index) => {
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
                        <Link
                          href={`/search?q=${encodeURIComponent(`"${r.text}"`)}`}
                        >
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
                <div className="flex items-center px-4">
                  {formatNumber(r.count)}
                </div>
                <div className="flex items-center px-4">
                  {formatNumber(r.docCount)}
                </div>
                <div className="flex items-center px-4">
                  {r.mentionsPerDocument.toFixed(2)}
                </div>
              </div>
            );
          })}
        </div>
      </div>
      <PageNumbers
        totalPages={data.totalPages}
        currentPage={page}
        pageLink={(nextPage) =>
          formatURL("/analytics/entities", {
            filter: newFilter,
            sortBy: "docs",
            page: nextPage,
            tags:
              new Set(values).union(new Set(defaultValues)).size ==
              defaultValues.length
                ? undefined
                : values.join(","),
          })
        }
      />
    </div>
  );
};
