"use client";
import React, { Fragment, useMemo } from "react";
import { cn } from "@/lib/utils/cn";
import { Hint } from "@/components/hint";
import { Button } from "@/components/ui/button";
import { SearchIcon } from "lucide-react";
import Link from "next/link";
import { parseAsStringEnum, useQueryState } from "nuqs";
import { ScrollableBox } from "@/components/scrolling/Scrollbox";

type DataProps = {
  points: { id: string; name: string; support: number }[];
};

export const TopicsListView = ({ points }: DataProps) => {
  const total = useMemo(
    () => Math.max(...points.map((p) => p.support)),
    [points],
  );
  const [tab] = useQueryState(
    "tab",
    parseAsStringEnum(["list", "chart"])
      .withDefault("list")
      .withOptions({ clearOnDefault: true }),
  );
  if (tab === "chart") {
    return null;
  }
  return (
    <ScrollableBox.ScrollArea outerClassName="p-0!">
      <div className="grid flex-1 grid-cols-1 md:grid-cols-[3fr_2fr]">
        {points
          .sort((a, b) => b.support - a.support)
          .map((topic, index) => (
            <Fragment key={topic.id}>
              <div
                className={cn(
                  "bg-row flex items-center gap-2 px-3 py-1",
                  index % 2 === 0 && "bg-alternate-row",
                )}
              >
                <Hint hint="Search the corpus for this topic" asChild>
                  <Button size="icon-xs" variant="ghost">
                    <SearchIcon />
                  </Button>
                </Hint>
                <Link href={`/analytics/topics/${topic.id}`} className="link">
                  {topic.name}
                </Link>
              </div>
              <div
                className={cn(
                  "bg-row hidden items-center px-3 py-1 md:flex",
                  index % 2 === 0 && "bg-alternate-row",
                )}
              >
                <div
                  className="bg-dodger-blue-500 h-1 justify-self-center"
                  style={{
                    width: `${Math.max(5, (topic.support / total) * 350)}px`,
                  }}
                />
              </div>
            </Fragment>
          ))}
      </div>
    </ScrollableBox.ScrollArea>
  );
};
