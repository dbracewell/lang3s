import { Chart, ChartData, CountType } from "@/features/reports/types";
import { SeriesFormType } from "@/features/reports/schema";
import {
  CartesianGrid,
  Label,
  Legend,
  Line,
  LineChart as RechartsLineChart,
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
import { DataTypeCategory } from "@/features/common/types";

type LineChartProps = {
  data: ChartData;
  xSeries: SeriesFormType;
  ySeries?: SeriesFormType;
  className?: string;
  countType: CountType;
  xDataType: DataTypeCategory;
};

function generateRainbowColors(n: number): string[] {
  const colors: string[] = [];
  for (let i = 0; i < n; i++) {
    // Hue ranges from 0 to 360 (red to red)
    const hue = Math.round((i * 360) / n);
    // Saturation and Lightness are set to 100% and 50% for vibrant colors
    colors.push(`hsl(${hue}, 100%, 50%)`);
  }
  return colors;
}

const chartConfig = {} satisfies ChartConfig;
export const LineChart = ({
  data,
  xSeries,
  xDataType,
  ySeries,
  className,
  countType,
}: LineChartProps) => {
  const uniqueSeries = [
    ...new Set(
      data.map((d) =>
        ySeries ? d.text2 : Chart.formatCountTypeName(countType),
      ),
    ),
  ].sort();

  const morphed = useMemo(() => {
    return Object.values(
      data.reduce(
        (agg, d) => {
          const series = xDataType === "number" ? d.value1 : d.text1;
          if (agg[series] == null) {
            agg[series] = {
              series,
              data: {},
            };
          }
          const catText = ySeries
            ? d.text2
            : Chart.formatCountTypeName(countType);
          if (agg[series].data[catText] == null) {
            agg[series].data = {
              ...agg[series].data,
              [catText]: 0,
            };
          }
          agg[series].data[catText] += Chart.getCount(d, countType);
          return agg;
        },
        {} as Record<
          string,
          { series: string | number; data: Record<string, number> }
        >,
      ),
    ).map((d) => ({ series: d.series, ...d.data }));
  }, [countType, data]);

  const myColor = generateRainbowColors(uniqueSeries.length);

  return (
    <ChartContainer config={chartConfig} className={cn("min-h-0", className)}>
      <RechartsLineChart
        accessibilityLayer
        data={morphed}
        margin={{
          top: 50,
          right: 20,
          left: 10,
          bottom: 50,
        }}
      >
        <CartesianGrid strokeDasharray="3 3" />
        <ChartTooltip cursor={false} content={<ChartTooltipContent />} />
        {uniqueSeries.map((s, i) => (
          <Line
            type="monotone"
            dataKey={s}
            stroke={myColor[i]}
            strokeWidth={2}
            activeDot={{ r: 8 }}
            key={s}
          />
        ))}
        <XAxis
          dataKey="series"
          type={xDataType === "number" ? "number" : "category"}
          tick={true}
          hide={false}
          label={
            <Label
              value={Chart.getAxisLabel(xSeries)}
              fontSize={13}
              fontWeight={600}
              className="mt-100"
              style={{
                fill: "var(--color-foreground)",
              }}
              position="bottom"
            />
          }
        />
        <YAxis
          type="number"
          label={
            <Label
              angle={-90}
              value={Chart.formatCountTypeName(countType)}
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
        <Legend
          layout="vertical"
          verticalAlign="top"
          align="right"
          wrapperStyle={{
            paddingLeft: "20px",
          }}
        />
      </RechartsLineChart>
    </ChartContainer>
  );
};
