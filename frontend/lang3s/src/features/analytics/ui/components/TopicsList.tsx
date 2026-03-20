"use client";
import React, { useEffect, useState } from "react";
import { cn } from "@/lib/utils/cn";
import { Hint } from "@/components/hint";
import { buttonVariants } from "@/components/ui/button";
import { ChevronLeftIcon, ChevronRightIcon, SearchIcon } from "lucide-react";
import Link from "next/link";
import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import { formatNumber, formatURL } from "@/lib/utils/formatters";
import { useChatContext } from "@/features/chat/hooks/useChatContext";
import { CorpusExplorerPoint } from "@/features/analytics/types";
import { useFindMultiTypeMinMaxValue } from "@/components/d3/hooks";

type DataProps = {
  points: CorpusExplorerPoint[];
};

const getType = (point: CorpusExplorerPoint) => point.type;

const getValue = (point: CorpusExplorerPoint) => point.value;

export const TopicsList = ({ points }: DataProps) => {
  const { setContext } = useChatContext();
  const valueRanges = useFindMultiTypeMinMaxValue({
    points: points,
    getType,
    getValue,
  });
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
        <h2 className="flex items-center gap-2 px-4"># of Documents</h2>
      </div>
      <ScrollableBox.ScrollArea outerClassName="p-0! flex-1 rounded-t-none">
        <div>
          {points
            .sort((a, b) => b.value - a.value)
            .map((topic, index) => (
              <TopicRow
                key={topic.id}
                topic={topic}
                normalizer={valueRanges}
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
  index,
  normalizer,
}: {
  topic: CorpusExplorerPoint;
  index: number;
  normalizer?: Record<
    string,
    {
      max: number;
      min: number;
    }
  >;
}) => {
  const numSubValues = Object.keys(topic.subvalues).length;
  const [numConceptsToDisplay, setNumConceptsToDisplay] = useState(
    Math.min(numSubValues, 10),
  );
  const hasMore = numConceptsToDisplay < numSubValues;
  if (!normalizer) {
    return null;
  }

  return (
    <details
      className={cn(
        "group bg-row flex w-full flex-col",
        index % 2 === 0 && "bg-alternate-row",
      )}
    >
      <summary className="group group-open:bg-heading grid flex-1 grid-cols-1 py-2 group-open:text-white md:grid-cols-[3fr_2fr]">
        <div className="flex items-center gap-2">
          <ChevronRightIcon className="ml-2 size-4 cursor-pointer group-open:rotate-90" />
          <div className="flex items-center gap-2 py-1 pr-3">
            <Hint hint="Search the corpus for this topic" asChild>
              <Link
                href={formatURL("/search", {
                  tid: topic.id,
                  placeholder: `TOPIC: ${topic.text}`,
                  isStrict: false,
                })}
                className={buttonVariants({
                  size: "icon-xs",
                  variant: "listButton",
                })}
              >
                <SearchIcon />
              </Link>
            </Hint>
            <Link
              href={`/analytics/topics/${topic.id}`}
              className="hover:text-dodger-blue-500 hover:underline group-open:hover:text-white"
            >
              {topic.text}
            </Link>
          </div>
        </div>
        <div className="hidden items-center gap-2 px-3 py-1 text-sm md:flex">
          {formatNumber(topic.value)}
          <div
            className="bg-dodger-blue-500 group-open:bg-dodger-blue-100 h-1 justify-self-center"
            style={{
              width: `${Math.max(5, (topic.value / normalizer["topic"].max) * 350)}px`,
            }}
          />
        </div>
      </summary>
      <div className="group-open:bg-heading px-3 py-1">
        <div className="grid flex-1 grid-cols-1 bg-green-600 py-1 text-white md:grid-cols-[3fr_2fr] dark:bg-green-700">
          <div className="pl-12">Concept</div>
          <div className="hidden pl-4 md:flex"># of Documents in Topic</div>
        </div>
        <div className="flex flex-col">
          {Object.entries(topic.subvalues)
            .slice(0, numConceptsToDisplay)
            .map(([key, value]) => (
              <div
                className={cn(
                  "grid flex-1 grid-cols-1 py-0.5 first:pt-1 odd:bg-green-100 even:bg-green-50 md:grid-cols-[3fr_2fr] dark:odd:bg-green-900 dark:even:bg-green-800",
                  !hasMore && "last:pb-1",
                )}
                key={key}
              >
                <div className="pl-12">{key}</div>
                <div className="hidden items-center gap-1 pl-4 md:flex">
                  {formatNumber(value)}
                  <div
                    className="h-1 justify-self-center bg-green-500 dark:bg-green-50"
                    style={{
                      width: `${Math.max(5, (value / topic.value) * 350)}px`,
                    }}
                  />
                </div>
              </div>
            ))}
          {hasMore && (
            <button
              className="w-full p-3 text-center text-sm text-white hover:underline"
              onClick={() => {
                setNumConceptsToDisplay((prev) => prev + 10);
              }}
            >
              Load More...
            </button>
          )}
        </div>
      </div>
    </details>
  );
};
