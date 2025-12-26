import { Chart, ChartData, CountType } from "@/features/reports/types";
import { SeriesType } from "@/features/reports/schema";
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

type LineChartProps = {
  data: ChartData;
  xSeries: SeriesType;
  ySeries: SeriesType;
  className?: string;
  countType: CountType;
};

const chartConfig = {} satisfies ChartConfig;
export const ScatterPlotChart = ({
  data,
  xSeries,
  ySeries,
  className,
  countType,
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
          top: 50,
          right: 20,
          left: 10,
          bottom: 100,
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
          allowDuplicatedCategory={xSeries.dataType === "number"}
          textAnchor="end"
          type={xSeries.dataType === "number" ? "number" : "category"}
          label={
            <Label
              value={Chart.getAxisLabel(xSeries)}
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
          type={ySeries.dataType === "number" ? "number" : "category"}
          allowDuplicatedCategory={ySeries.dataType === "number"}
          label={
            <Label
              angle={-90}
              value={Chart.getAxisLabel(ySeries)}
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
