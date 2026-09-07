import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ChartNoAxesGanttIcon, SquareArrowUpRightIcon } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import React from "react";
import Link from "next/link";

export const TopicSummary = ({
  summary,
}: {
  summary?: { name: string; support: number }[];
}) => {
  if (!summary) {
    return (
      <Card className="w-full">
        <CardContent className="flex h-full w-full flex-col items-center justify-center">
          <ChartNoAxesGanttIcon className="text-muted-foreground size-20" />
          <span className="text-muted-foreground">
            No summary generated yet.
          </span>
        </CardContent>
      </Card>
    );
  }
  const maxValue = summary?.[0]?.support ?? 1;
  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="text-xl">Top Topics</CardTitle>
        <CardDescription>
          Topics appearing in the most number of sentences
        </CardDescription>
        <CardAction>
          <Link href={"/analytics/topics"}>
            <SquareArrowUpRightIcon className="hover:text-dodger-blue-500 text-muted-foreground size-6" />
          </Link>
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col">
        {summary.map((topic, index) => (
          <TopicRow
            key={topic.name}
            topic={topic}
            normalizer={maxValue}
            index={index}
          />
        ))}
      </CardContent>
    </Card>
  );
};

const TopicRow = ({
  topic,
  normalizer,
  index,
}: {
  topic: { name: string; support: number };
  normalizer: number;
  index: number;
}) => {
  return (
    <div
      className={cn(
        "bg-row flex items-center gap-2 p-1",
        index % 2 === 0 && "bg-alternate-row",
      )}
    >
      <div className="w-1/2">{topic.name}</div>
      <div className="hidden w-1/2 items-center px-3 py-1 md:flex">
        <div
          className="bg-dodger-blue-500 h-1 justify-self-center"
          style={{
            width: `${(topic.support / normalizer) * 100}%`,
          }}
        />
      </div>
    </div>
  );
};
