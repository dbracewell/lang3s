"use client";
import { Spinner } from "@/components/Spinner";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useTRPCQuery } from "@/lib/trpc/use-queries";
import { XIcon } from "lucide-react";
import Link from "next/link";
import { ResponsiveContainer, Tooltip, Treemap } from "recharts";
import { TreemapNode } from "recharts/types/util/types";
import { useEntitySearchParams } from "@/features/analytics/hooks/useEntitySearchParams";

const COLORS = [
  "#84bff5", //dodger-blue-300
  "oklch(78.5% 0.115 274.713)", //indigo-300,
  "oklch(86.9% 0.022 252.894)", //slate-300
  "oklch(82.7% 0.119 306.383)", //purple-300
  "oklch(80.8% 0.114 19.571)", //red-300
  "oklch(82.8% 0.111 230.318)", //sky-300
  "oklch(87% 0 0)", //neutral-300
  "oklch(87.9% 0.169 91.605)", //amber-300
  "oklch(87.1% 0.006 286.286)", //zinc-300
];

export const EntityCoOccurrenceVisualization = () => {
  const [params, setParams] = useEntitySearchParams();

  const { data, isLoading } = useTRPCQuery((trpc) =>
    trpc.analytics.getAnnotationCoOccurrence.queryOptions(
      {
        leftValue: params.entityType,
        leftText: params.entity,
        rightValues: params.tags,
      },
      {
        enabled: !!params.entity && !!params.entityType && !params.showEvents,
      },
    ),
  );

  if (params.showEvents || !params.entity || !params.entityType) {
    return null;
  }

  const entityTypeName = params.entityType.split(".").slice(-1)[0];
  return (
    <Card className="absolute top-0 left-0 z-10 h-full w-full">
      <CardHeader>
        <CardTitle className="text-2xl">
          Other entities mentioned with{" "}
          <span className="text-dodger-blue-500 font-black">
            {params.entity} ({entityTypeName})
          </span>
        </CardTitle>
        <CardDescription>
          Displays the number of times each entity was mentioned in the same
          sentence as{" "}
          <span className="font-bold">
            {params.entity} ({entityTypeName})
          </span>
          .
        </CardDescription>
        <CardAction>
          <Button
            variant="ghost"
            onClick={() => {
              setParams({
                entity: "",
                entityType: "",
              });
            }}
          >
            <XIcon />
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="flex w-full flex-1 flex-col p-3">
        {(isLoading || !data) && <Spinner />}
        {data && (
          <ResponsiveContainer width="100%" height="100%">
            <Treemap
              width={400}
              height={200}
              data={data.map((r) => ({
                name: `${r.e2} - ${r.e2Type} (${r.count})`,
                size: r.count * 100,
              }))}
              dataKey="size"
              aspectRatio={4 / 3}
              stroke="#fff"
              animationDuration={0}
              fill="#8884d8"
              //@ts-ignore
              content={(props) => (
                <CustomizedContent source={params.entity} {...props} />
              )}
            >
              <Tooltip content={<CustomTooltip />} />
            </Treemap>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
};

const CustomTooltip = ({
  active,
  label,
  payload,
}: {
  active?: boolean;
  label?: string;
  payload?: any[];
}) => {
  if (active && payload && payload.length) {
    return (
      <div className="rounded-md border border-slate-900 bg-slate-700 px-3 py-1 text-xs text-white shadow-lg">
        <p>{payload[0].payload.name}</p>
      </div>
    );
  }
  return null;
};

const CustomizedContent = (props: TreemapNode) => {
  const { source, root, depth, x, y, width, height, index, name } = props;

  if (name == null) {
    return <></>;
  }

  let parts = name.split(" - ");
  let shortName =
    parts.length > 0 ? parts[0].slice(0, Math.floor(width / 10)).trim() : name;
  if (shortName.length < parts[0].length) {
    shortName += "...";
  }

  let secondLine = parts.length > 1 ? parts[1].trim() : "";

  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        style={{
          fill:
            depth < 2
              ? COLORS[
                  Math.floor((index / root.children.length) * COLORS.length)
                ]
              : "#ffffff00",
          stroke: "#fff",
          strokeWidth: 2 / (depth + 1e-10),
          strokeOpacity: 1 / (depth + 1e-10),
        }}
      />
      <Link
        href={`/search?q=${encodeURIComponent(
          '"' + source + '" "' + name.split(" - ")[0] + '"',
        )}&type=sentence`}
      >
        <text
          x={x + width / 2}
          y={y + height / 2}
          textAnchor="middle"
          strokeWidth={0}
          fill="#000"
          fontWeight={800}
          fontSize={index < 10 ? "14px" : index < 25 ? "10px" : "6px"}
        >
          <tspan>{shortName}</tspan>
          <tspan
            dy="1.5em"
            x={x + width / 2}
            fill="#333"
            fontSize={index < 10 ? "10px" : index < 25 ? "6px" : "4px"}
          >
            {secondLine}
          </tspan>
        </text>
      </Link>
    </g>
  );
};
