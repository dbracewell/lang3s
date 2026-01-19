"use client";
import { useEntitySearchParams } from "@/features/analytics/hooks/useEntitySearchParams";
import { useTRPCQuery } from "@/lib/trpc/use-queries";
import { Spinner } from "@/components/Spinner";
import { useMemo, useRef, useState } from "react";
import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import { cn } from "@/lib/utils/cn";
import { Hint } from "@/components/hint";
import { randomAlphaUnderscore } from "@/lib/utils/random";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export const EntityMetrics = () => {
  const [params] = useEntitySearchParams();
  const [metric, setMetric] = useState("affinity");

  const { data: cooc } = useTRPCQuery((trpc) =>
    trpc.analytics.getAnnotationLoners.queryOptions({
      values: params.tags,
    }),
  );
  const { data: entropy } = useTRPCQuery((trpc) =>
    trpc.analytics.getAnnotationEntropy.queryOptions({
      values: params.tags,
    }),
  );

  return (
    <div className="mt-2 flex h-full min-h-0 flex-1 flex-col gap-3 p-2">
      <Select value={metric} onValueChange={setMetric}>
        <SelectTrigger>
          <SelectValue placeholder="Select Metric..." />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={"affinity"}>Affinity Score</SelectItem>
          <SelectItem value={"topic"}>Topic Focus</SelectItem>
        </SelectContent>
      </Select>
      <div className="bg-card flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border p-2">
        <ScrollableBox.ScrollArea outerClassName="border-0!">
          {metric === "affinity" && (
            <Chart
              title="Affinity Score"
              description="A measure of how strongly an entity is connected to other entities. It calculates how likely an entities is to be mentioned in sentences with outher entities."
              lowSubtitle="Less likely to be mentioned with others."
              highSubtitle="More likely to be mentioned with others."
              data={cooc}
            />
          )}
          {metric === "topic" && (
            <Chart
              title="Topic Focus"
              description="A measure of specificity. It calculates whether an entity is dedicated to a single topic or spread across many."
              lowSubtitle="Limited focus on a few topics."
              highSubtitle="Broad focus across many topics."
              data={entropy}
            />
          )}
        </ScrollableBox.ScrollArea>
      </div>
    </div>
  );
};

const Chart = ({
  title,
  description,
  lowSubtitle,
  highSubtitle,
  data,
}: {
  title: string;
  description: string;
  lowSubtitle: string;
  highSubtitle: string;
  data?: {
    entityId: string;
    entityType: string;
    normScore: number;
    rawScore: number;
    category: string;
  }[];
}) => {
  const minHeight = 50;
  const maxHeight = 250;
  const containerRef = useRef<HTMLDivElement | null>(null);
  const tooltipRef = useRef<HTMLDivElement | null>(null);
  const [position, setPosition] = useState<{ x: number; y: number }>({
    x: 0,
    y: 0,
  });
  return (
    <div className="flex w-full flex-col">
      <div className="mb-6">
        <div className="mb-2 flex items-center gap-3">
          <h2 className="p-2 text-xl font-bold">{title}</h2>
          <h3 className="text-muted-foreground max-w-lg text-xs font-semibold">
            {description}
          </h3>
        </div>
        <div className="flex items-center px-5 text-xs font-medium">
          <h4 className="w-1/2 text-center">{lowSubtitle}</h4>
          <h4 className="w-1/2 text-center">{highSubtitle}</h4>
        </div>
      </div>
      <div
        className="relative mx-auto flex"
        style={{ height: 2 * maxHeight }}
        ref={containerRef}
      >
        <div
          className="absolute z-10 h-14 w-fit shrink-0 -translate-x-1/2 truncate rounded-lg border border-slate-900 bg-slate-700 p-3 text-center text-xs whitespace-pre-line text-white"
          style={{
            visibility: "hidden",
            bottom: containerRef.current
              ? containerRef.current.getBoundingClientRect().bottom -
                position.y +
                30
              : undefined,
            left: containerRef.current
              ? position.x >=
                containerRef.current.getBoundingClientRect().right - 100
                ? position.x - 100
                : position.x
              : undefined,
          }}
          ref={tooltipRef}
        ></div>
        {data == null && <Spinner />}
        {data?.map((entry) => {
          return (
            <div
              className="hover:bg-alternate-row flex flex-col select-none"
              key={`${entry.entityId}=${entry.entityType}`}
              onMouseMove={(e) => {
                if (tooltipRef.current && containerRef.current) {
                  tooltipRef.current.style.visibility = `visible`;
                  setPosition({ x: e.clientX, y: e.clientY });
                  tooltipRef.current.textContent = `${entry.entityId}\n(${entry.entityType.split(".").slice(-1)[0]})`;
                }
              }}
              onMouseLeave={(e) => {
                if (tooltipRef.current && containerRef.current) {
                  tooltipRef.current.style.visibility = `hidden`;
                }
              }}
            >
              <div className="border-dodger-blue-900 dark:border-dodger-blue-300 flex h-1/2 shrink-0 items-end border-b-1 px-0.5 pb-1">
                {entry.category === "high" ? (
                  <Bar
                    entity={entry.entityId}
                    rawScore={entry.rawScore}
                    height={Math.floor(
                      minHeight + (maxHeight - minHeight) * entry.normScore,
                    )}
                  />
                ) : (
                  <Title
                    entity={entry.entityId}
                    entityType={entry.entityType}
                    category={entry.category}
                  />
                )}
              </div>
              <div className="flex h-1/2 shrink-0 items-start px-0.5 pt-1">
                {entry.category === "low" ? (
                  <Bar
                    entity={entry.entityId}
                    rawScore={entry.rawScore}
                    height={Math.floor(
                      minHeight + (maxHeight - minHeight) * entry.normScore,
                    )}
                  />
                ) : (
                  <Title
                    entity={entry.entityId}
                    entityType={entry.entityType}
                    category={entry.category}
                  />
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const Bar = ({
  entity,
  rawScore,
  height,
}: {
  entity: string;
  rawScore: number;
  height: number;
}) => {
  const [, setParams] = useEntitySearchParams();
  return (
    <div
      className="bg-primary relative w-5 cursor-pointer md:w-7"
      style={{
        height,
      }}
      onClick={() => {
        setParams({
          filter: entity,
          view: "list",
        });
      }}
    >
      <div
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 rotate-180 text-xs text-white"
        style={{
          writingMode: "vertical-lr",
          textOrientation: "sideways-right",
        }}
      >
        {rawScore.toFixed(2)}
      </div>
    </div>
  );
};

const Title = ({
  entity,
  entityType,
  category,
}: {
  entity: string;
  entityType: string;
  category: string;
}) => {
  const [, setParams] = useEntitySearchParams();
  return (
    <div
      className={cn(
        "h-full rotate-180 truncate px-2 text-xs tracking-wide hover:underline md:text-sm",
        category === "high" && "text-right",
      )}
      style={{
        writingMode: "vertical-lr",
        textOrientation: "sideways-right",
      }}
    >
      <span
        className="cursor-pointer"
        onClick={() => {
          setParams({
            filter: entity,
            view: "list",
          });
        }}
      >
        {entity} ({entityType.split(".").slice(-1)[0]})
      </span>
    </div>
  );
};
