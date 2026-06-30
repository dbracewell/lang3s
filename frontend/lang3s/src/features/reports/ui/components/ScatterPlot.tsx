import { SeriesFormType } from "@/features/reports/schema";
import {
  CartesianGrid,
  Label,
  Scatter,
  ScatterChart as ReactsScatterPlot,
  XAxis,
  YAxis,
} from "recharts";
import { cn } from "@/lib/utils/cn";
import {
  ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";
import { useMemo } from "react";
import type { ChartData, CountType, DataCategory } from "@/clients/analytics";
import { formatAxisLabel } from "@/features/reports/lib/formatters";

type LineChartProps = {
  data: ChartData[];
  xSeries: SeriesFormType;
  ySeries: SeriesFormType;
  className?: string;
  countType: CountType;
  xDataType: DataCategory;
  yDataType: DataCategory;
};

const chartConfig = {} satisfies ChartConfig;
export const ScatterPlotChart = ({
  data,
  xSeries,
  ySeries,
  className,
  countType,
  xDataType,
  yDataType,
}: LineChartProps) => {
  const morphed = useMemo(() => {
    return data.map((d) => ({
      x: d.value1,
      y: d.value2,
    }));
  }, [data]);

  return (
    <ChartContainer config={chartConfig} className={cn("min-h-0", className)}>
      <ReactsScatterPlot
        data={morphed}
        margin={{
          top: 20,
          right: 20,
          left: 10,
          bottom: 20,
        }}
      >
        <CartesianGrid strokeDasharray="3 3" />
        <ChartTooltip cursor={false} content={<ChartTooltipContent />} />
        <Scatter data={morphed} fill="var(--color-dodger-blue-500)" />
        <XAxis
          dataKey="x"
          tick={true}
          hide={false}
          writingMode="sideways-lr"
          allowDuplicatedCategory={xDataType === "number"}
          textAnchor="end"
          type={xDataType === "number" ? "number" : "category"}
          label={
            <Label
              value={formatAxisLabel(xSeries)}
              fontSize={13}
              fontWeight={600}
              style={{
                fill: "var(--color-foreground)",
              }}
              position="bottom"
            />
          }
        />
        <YAxis
          dataKey={"y"}
          tick={true}
          hide={false}
          type={yDataType === "number" ? "number" : "category"}
          allowDuplicatedCategory={yDataType === "number"}
          label={
            <Label
              angle={-90}
              value={formatAxisLabel(ySeries)}
              style={{
                fill: "var(--color-foreground)",
                textAnchor: "middle",
              }}
              fontSize={13}
              fontWeight={600}
              position="insideLeft"
            />
          }
        />
      </ReactsScatterPlot>
    </ChartContainer>
  );
};
