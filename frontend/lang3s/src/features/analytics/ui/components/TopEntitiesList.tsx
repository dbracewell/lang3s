"use client";

import { Hint } from "@/components/hint";
import { Button } from "@/components/ui/button";
import { useTRPCQuery } from "@/lib/trpc/use-queries";
import {
  ArrowDownIcon,
  ChartNetworkIcon,
  CircleQuestionMarkIcon,
  SearchIcon,
  SquareActivityIcon,
  XIcon,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { formatNumber } from "@/lib/utils/formatters";
import { PageNumbers } from "@/components/PageNumbers";
import { useEntitySearchParams } from "@/features/analytics/hooks/useEntitySearchParams";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group";
import { Skeleton } from "@/components/ui/skeleton";
import { RouterOutputs } from "@/lib/trpc/types";
import { useChatContext } from "@/features/chat/hooks/useChatContext";

export const TopEntitiesList = () => {
  const [params, setParams] = useEntitySearchParams();
  const { setContext } = useChatContext();
  const { data, isLoading, error } = useTRPCQuery((trpc) =>
    trpc.analytics.getAnnotationCounts.queryOptions({
      page: params.page,
      sortBy: params.sortBy,
      filter: !!params.filter.trim() ? params.filter : undefined,
      values: params.tags,
    }),
  );

  useEffect(() => {
    if (params.entityType && params.entity) {
      return;
    }
    if (data == null) {
      setContext("");
    } else {
      setContext(
        data.results.map((row) => `${row.content}/${row.value}`).join("\n"),
      );
    }
  }, [data, params]);

  if (error != null) {
    console.log(error);
    throw error;
  }

  if (isLoading || data == null) {
    return <SkeletonPage />;
  }

  console.log(data.results[0]);

  return (
    <div className="mx-auto flex min-h-0 w-full flex-1 flex-col gap-2 p-3">
      <div className="flex items-center gap-5">
        <Filter />
        <div className="hidden flex-1 text-lg font-semibold md:block">
          {formatNumber(data.total)} total Entities
        </div>
      </div>
      <div className="flex flex-1 flex-col overflow-hidden rounded-lg border bg-white shadow dark:bg-zinc-900">
        <div className="bg-heading grid grid-cols-5 p-2 font-semibold text-white">
          <div className="text-center">Entity</div>
          <div className="text-center">Entity Type</div>
          <SortableHeaderColumn
            sortBy={"mention_count"}
            text={"Mention Count"}
            hint={`Number of times this entity is mentioned\n(Includes multiple mentions per document.)`}
          />
          <SortableHeaderColumn
            sortBy={"document_count"}
            text={"Document Count"}
            hint={"Number of documents in which this entity appears"}
          />
          <SortableHeaderColumn
            sortBy={"mentions_per_document"}
            text={"Mentions Per Document"}
            hint={
              "Average number of times the entity is mentioned in documents in which it appears."
            }
          />
        </div>
        <div className="scrollable flex-1">
          {data.results.map((r) => {
            return <EntityRow entity={r} key={`${r.content}-${r.value}`} />;
          })}
        </div>
      </div>
      <PageNumbers
        totalPages={data.totalPages}
        currentPage={params.page}
        pageLink={(nextPage) => setParams({ page: nextPage })}
      />
    </div>
  );
};

const EntityRow = ({
  entity,
}: {
  entity: RouterOutputs["analytics"]["getAnnotationCounts"]["results"][number];
}) => {
  const [, setParams] = useEntitySearchParams();
  return (
    <div className="hover:bg-accent even:bg-alternate-row bg-row grid h-10 grid-cols-5 divide-x text-sm hover:font-bold">
      <div className="group flex items-center justify-between border-r px-4">
        <div className="mr-4 truncate">{entity.content}</div>
        <div className="hidden items-center gap-2 group-hover:flex">
          <Hint asChild hint={`Search for ${entity.content} in documents.`}>
            <Button
              asChild
              variant="ghost"
              size="icon-sm"
              className="hover:bg-dodger-blue-500 hover:text-white"
            >
              <Link
                href={`/search?q=${encodeURIComponent(`"${entity.content}"`)}`}
              >
                <SearchIcon />
              </Link>
            </Button>
          </Hint>
          <Hint
            asChild
            hint={`Examine entities mentioned with ${entity.content}.`}
          >
            <Button
              variant="ghost"
              size="icon-sm"
              className="hover:bg-dodger-blue-500 hover:text-white"
              onClick={() => {
                setParams({
                  entity: entity.content,
                  entityType: entity.path,
                });
              }}
            >
              <SquareActivityIcon />
            </Button>
          </Hint>
          <Hint
            asChild
            hint={`Examine the events involving ${entity.content}.`}
          >
            <Button
              variant="ghost"
              size="icon-sm"
              className="hover:bg-dodger-blue-500 hover:text-white"
              onClick={() => {
                setParams({
                  showEvents: true,
                  entity: entity.content,
                  entityType: entity.path,
                });
              }}
            >
              <ChartNetworkIcon />
            </Button>
          </Hint>
        </div>
      </div>
      <div className="flex items-center px-4">
        {entity.value.split(".").slice(-1)[0]}
      </div>
      <div className="flex items-center px-4">
        {formatNumber(entity.mention_count)}
      </div>
      <div className="flex items-center px-4">
        {formatNumber(entity.document_count)}
      </div>
      <div className="flex items-center px-4">
        {entity.mentions_per_document.toFixed(2)}
      </div>
    </div>
  );
};

const SortableHeaderColumn = ({
  sortBy,
  text,
  hint,
}: {
  sortBy: "mentions_per_document" | "mention_count" | "document_count";
  text: string;
  hint: string;
}) => {
  const [params, setParams] = useEntitySearchParams();
  return (
    <div className="flex items-center justify-center gap-2">
      {params.sortBy === sortBy ? (
        <span className="flex items-center">
          <ArrowDownIcon className="mr-2 size-4" /> {text}
        </span>
      ) : (
        <button
          type="button"
          className="hover:underline"
          onClick={() => {
            setParams({ sortBy });
          }}
        >
          {text}
        </button>
      )}
      <Hint hint={hint}>
        <CircleQuestionMarkIcon className="size-4" />
      </Hint>
    </div>
  );
};

const Filter = () => {
  const [params, setParams] = useEntitySearchParams();
  const [filter, setFilter] = useState<string>("");
  useEffect(() => {
    setFilter(params.filter);
  }, [params.filter]);

  return (
    <InputGroup className="max-w-md">
      <InputGroupInput
        placeholder="Filter by entity (Press enter to search)..."
        value={filter ?? ""}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            setParams({ filter, page: 1 });
          }
        }}
        onChange={(e) => setFilter(e.target.value)}
      />
      {!!filter.trim() && (
        <InputGroupAddon align="inline-end">
          <InputGroupButton
            variant="destructiveGhost"
            className="border-0!"
            size="icon-xs"
            type="button"
            onClick={() => {
              if (params.filter === filter) {
                setParams({ filter: "" });
              } else {
                setFilter("");
              }
            }}
          >
            <XIcon />
          </InputGroupButton>
        </InputGroupAddon>
      )}
    </InputGroup>
  );
};

const SkeletonPage = () => {
  return (
    <div className="flex min-h-0 w-full flex-1 flex-col gap-2 p-3">
      <div className="flex items-center gap-5">
        <Skeleton className="h-10 w-md" />
        <Skeleton className="h-10 w-sm" />
      </div>
      <div className="flex flex-1 flex-col overflow-hidden rounded-lg border bg-white shadow dark:bg-zinc-900">
        <Skeleton className="h-full w-full" />
      </div>
      <div className="flex justify-end">
        <Skeleton className="h-10 w-md" />
      </div>
    </div>
  );
};
