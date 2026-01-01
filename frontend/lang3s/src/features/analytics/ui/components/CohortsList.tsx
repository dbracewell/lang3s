"use client";
import { useTabParams } from "@/features/analytics/hooks/useTabParams";
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
import { parseAsString, useQueryState } from "nuqs";
import { useDebounce } from "@/hooks/useDebounce";
import { parseAsInteger } from "nuqs/server";
import { CohortView } from "@/features/analytics/ui/components/CohortView";
import { cn } from "@/lib/utils/cn";

export const CohortsList = ({
  clusters,
}: {
  clusters: { id: string; name: string; type: string }[][];
}) => {
  const [tabs] = useTabParams();
  const [searchQuery, setSearchQuery] = useQueryState(
    "q",
    parseAsString.withDefault("").withOptions({ clearOnDefault: true }),
  );
  const [selectedCohort, setSelectedCohort] = useQueryState(
    "c",
    parseAsInteger.withDefault(-1).withOptions({ clearOnDefault: true }),
  );
  const debouncedQuery = useDebounce(searchQuery, 500);
  if (tabs !== "list") {
    return null;
  }

  if (selectedCohort >= 0 && selectedCohort <= clusters.length) {
    return <CohortView cohort={clusters[selectedCohort]} />;
  }

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col gap-2">
      <InputGroup className="max-w-md">
        <InputGroupInput
          value={searchQuery}
          placeholder={`Search for an entity in the cohorts list`}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
        {!!searchQuery.trim() && (
          <InputGroupAddon align="inline-end">
            <InputGroupButton
              variant="destructiveGhost"
              className="border-0!"
              size="icon-xs"
              type="button"
              onClick={() => setSearchQuery("")}
            >
              <XIcon />
            </InputGroupButton>
          </InputGroupAddon>
        )}
      </InputGroup>
      <div className="scrollable grid flex-1 grid-cols-1 gap-3 md:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
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
                <button type="button" onClick={() => setSelectedCohort(name)}>
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
