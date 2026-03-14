"use client";
import React, { Fragment, useEffect, useMemo } from "react";
import { cn } from "@/lib/utils/cn";
import { Hint } from "@/components/hint";
import { buttonVariants } from "@/components/ui/button";
import { CircleQuestionMarkIcon, SearchIcon } from "lucide-react";
import Link from "next/link";
import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import { formatURL } from "@/lib/utils/formatters";
import { useChatContext } from "@/features/chat/hooks/useChatContext";

type DataProps = {
  points: { id: string; text: string; value: number }[];
};

export const TopicsList = ({ points }: DataProps) => {
  const total = useMemo(
    () => Math.max(...points.map((p) => p.value)),
    [points],
  );
  const { setContext } = useChatContext();

  useEffect(() => {
    const context = points
      .map((p) => `TopicId: ${p.id} TopicName: ${p.text}`)
      .join("\n");
    setContext(context);
  }, [points]);

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
            .sort((a, b) => b.value - a.value)
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
  topic: { text: string; id: string; value: number };
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
              placeholder: `TOPIC: ${topic.text}`,
              isStrict: false,
            })}
            className={buttonVariants({ size: "icon-xs", variant: "ghost" })}
          >
            <SearchIcon />
          </Link>
        </Hint>
        <Link
          href={`/analytics/topics/${topic.id}`}
          className="hover:text-dodger-blue-500 hover:underline"
        >
          {topic.text}
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
            width: `${Math.max(5, (topic.value / normalizer) * 350)}px`,
          }}
        />
      </div>
    </>
  );
};
