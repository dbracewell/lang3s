"use client";
import React, { Fragment, useMemo } from "react";
import { cn } from "@/lib/utils/cn";
import { Hint } from "@/components/hint";
import { Button, buttonVariants } from "@/components/ui/button";
import { CircleQuestionMarkIcon, SearchIcon } from "lucide-react";
import Link from "next/link";
import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import { useTabParams } from "@/features/analytics/hooks/useTabParams";
import { formatURL } from "@/lib/utils/formatters";

type DataProps = {
  points: { id: string; name: string; support: number }[];
};

export const TopicsListView = ({ points }: DataProps) => {
  const total = useMemo(
    () => Math.max(...points.map((p) => p.support)),
    [points],
  );
  const [tab] = useTabParams();
  if (tab === "chart") {
    return null;
  }
  return (
    <div className="flex min-h-0 flex-col">
      <div className="bg-heading grid grid-cols-1 rounded-t-lg border border-b-0 px-4 py-1 font-bold text-white md:grid-cols-[3fr_2fr]">
        <h2>Topic</h2>
        <h2 className="flex items-center gap-2 px-4">
          Support
          <Hint hint={`Number of sentences expressing this topic`}>
            <CircleQuestionMarkIcon className="size-4" />
          </Hint>
        </h2>
      </div>
      <ScrollableBox.ScrollArea outerClassName="p-0! flex-1 rounded-t-none">
        <div className="grid flex-1 grid-cols-1 md:grid-cols-[3fr_2fr]">
          {points
            .sort((a, b) => b.support - a.support)
            .map((topic, index) => (
              <TopicRow
                key={topic.id}
                topic={topic}
                normalizer={total}
                index={index}
              />
            ))}
        </div>
      </ScrollableBox.ScrollArea>
    </div>
  );
};

const TopicRow = ({
  topic,
  normalizer,
  index,
}: {
  topic: { name: string; id: string; support: number };
  normalizer: number;
  index: number;
}) => {
  return (
    <>
      <div
        className={cn(
          "bg-row flex items-center gap-2 px-3 py-1",
          index % 2 === 0 && "bg-alternate-row",
        )}
      >
        <Hint hint="Search the corpus for this topic" asChild>
          <Link
            href={formatURL("/search", {
              tid: topic.id,
              placeholder: `TOPIC: ${topic.name}`,
              isStrict: false,
            })}
            className={buttonVariants({ size: "icon-xs", variant: "ghost" })}
          >
            <SearchIcon />
          </Link>
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
            width: `${Math.max(5, (topic.support / normalizer) * 350)}px`,
          }}
        />
      </div>
    </>
  );
};
