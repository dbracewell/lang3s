"use client";
import Link from "next/link";
import { formatURL } from "@/lib/utils/formatters";
import { getColorName } from "@/lib/utils/colors";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group";
import { SquareArrowUpRightIcon, XIcon } from "lucide-react";
import { useDebounce } from "@/hooks/useDebounce";
import { CohortView } from "@/features/analytics/ui/components/CohortView";
import { cn } from "@/lib/utils/cn";
import { useEffect } from "react";
import { useChatContext } from "@/features/chat/hooks/useChatContext";
import { useCohortsParams } from "@/features/analytics/hooks/useCohortsParams";

export const CohortsList = ({
  clusters,
}: {
  clusters: { id: string; name: string; type: string }[][];
}) => {
  const [params, setParams] = useCohortsParams();
  const { setContext } = useChatContext();

  useEffect(() => setContext(""), [params.c]);

  const debouncedQuery = useDebounce(params.q, 500);
  if (params.tab !== "list") {
    return null;
  }

  if (params.c >= 0 && params.c <= clusters.length) {
    return <CohortView cohort={clusters[params.c]} />;
  }

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col gap-2">
      <InputGroup className="max-w-md">
        <InputGroupInput
          value={params.q}
          placeholder={`Search for an entity in the cohorts list`}
          onChange={(e) => setParams({ q: e.target.value })}
        />
        {!!params.q.trim() && (
          <InputGroupAddon align="inline-end">
            <InputGroupButton
              variant="destructiveGhost"
              className="border-0!"
              size="icon-xs"
              type="button"
              onClick={() => setParams({ q: "" })}
            >
              <XIcon />
            </InputGroupButton>
          </InputGroupAddon>
        )}
      </InputGroup>
      <div className="scrollable grid flex-1 grid-cols-1 gap-3 @xl:grid-cols-2 @3xl:grid-cols-3 @5xl:grid-cols-4 @7xl:grid-cols-5">
        {clusters.map((ids, name) => {
          const filtered = !!debouncedQuery.trim()
            ? ids.filter((p) =>
                p.name
                  .toLowerCase()
                  .startsWith(debouncedQuery.trim().toLowerCase()),
              )
            : ids;

          if (filtered.length === 0) {
            return null;
          }
          const sorted = [...ids];
          sorted.sort((a, b) => {
            if (!!debouncedQuery.trim()) {
              if (
                a.id
                  .toLowerCase()
                  .startsWith(debouncedQuery.trim().toLocaleLowerCase())
              ) {
                return -1;
              }
              if (
                b.id
                  .toLowerCase()
                  .startsWith(debouncedQuery.trim().toLocaleLowerCase())
              ) {
                return -1;
              }
            }
            return a.id.localeCompare(b.id);
          });

          return (
            <div
              key={ids[0].id}
              style={{
                backgroundColor: `var(--color-${getColorName(ids[0].id).toLowerCase()}-500)`,
                opacity: filtered.length > 0 ? `100%` : `20%`,
              }}
              className={cn(
                "shadow-shadow flex h-[300px] flex-col overflow-hidden rounded-lg border text-sm text-gray-50 shadow-sm hover:bg-zinc-300/80 dark:hover:bg-white/10",
                ["YELLOW"].includes(getColorName(ids[0].id)) &&
                  "text-stone-900",
              )}
            >
              <div className="bg-card text-md text-card-foreground flex items-center justify-between border-b p-1 font-bold">
                <h2 className="truncate">
                  {ids[0].name}{" "}
                  <span className="text-muted-foreground text-xs">
                    ({ids.length} entities)
                  </span>
                </h2>
                <button type="button" onClick={() => setParams({ c: name })}>
                  <SquareArrowUpRightIcon className="hover:text-dodger-blue-500 size-4" />
                </button>
              </div>
              <div className="scrollable flex-1 p-2 pt-0">
                {sorted.map((p) => (
                  <Link
                    href={formatURL("/search", {
                      q: `"${p.name}"`,
                      isStrict: true,
                    })}
                    key={p.id}
                    className="block hover:underline"
                  >
                    {p.name}{" "}
                    <span className="text-xs font-medium">
                      {p.type.split(".").slice(-1)[0]}
                    </span>
                  </Link>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
