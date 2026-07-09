import {
  Bar,
  BarChart as RechartBarChart,
  Label,
  LabelList,
  XAxis,
  YAxis,
} from "recharts";
import {
  ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";
import { cn } from "@/lib/utils/cn";
import { useTheme } from "next-themes";
import { capitalize } from "@/lib/utils/formatters";
import type { ChartData, CountType, SeriesType } from "@/clients/analytics";
import {
  selectCountDataKey,
  truncateLabel,
} from "@/features/reports/lib/utils";

type BarChartProps = {
  data: ChartData[];
  xAxisType: SeriesType;
  xAxisValue: string;
  countType: CountType;
  className?: string;
};

const chartConfig = {} satisfies ChartConfig;

const BarChart = ({
  xAxisType,
  xAxisValue,
  countType,
  data,
  className,
}: BarChartProps) => {
  const { theme } = useTheme();
  const countDataKey = selectCountDataKey(countType);
  return (
    <ChartContainer config={chartConfig} className={cn("min-h-0", className)}>
      <RechartBarChart
        accessibilityLayer
        data={data}
        margin={{ bottom: 20, left: 20, right: 20, top: 20 }}
      >
        <XAxis
          dataKey="text1"
          // allowDuplicatedCategory={false}
          hide={false}
          label={
            <Label
              value={xAxisType}
              fontSize={13}
              fontWeight={600}
              style={{
                fill: "var(--color-foreground)",
              }}
              position="middle"
            />
          }
          tick={true}
          type="category"
          interval={0}
        />
        <YAxis
          dataKey={countDataKey}
          hide={false}
          tick={true}
          label={
            <Label
              angle={-90}
              value={capitalize(
                countDataKey.replace(/[A-Z]/g, (letter) => ` ${letter}`),
              )}
              style={{
                fill: theme === "dark" ? "white" : "black",
                textAnchor: "middle",
              }}
              fontSize={13}
              fontWeight={600}
              position="insideLeft"
            />
          }
          tickCount={10}
          type="number"
        />
        <ChartTooltip
          cursor={false}
          content={<ChartTooltipContent indicator="line" />}
        />
        <Bar
          dataKey={countDataKey}
          fill="var(--color-dodger-blue-500)"
          activeBar={{
            fill: "var(--color-dodger-blue-300)",
            stroke: "var(--color-dodger-blue-100)",
          }}
          radius={[10, 10, 0, 0]}
        >
          <LabelList
            dataKey="text1"
            content={(props) => {
              const { x, y, width, value, height } = props;
              const short = truncateLabel(
                String(value),
                Number(height) / 2 / 8,
              );
              if (Number(x) <= 0) {
                return null;
              }
              return (
                <g>
                  <text
                    x={Number(x) + Number(width) / 2}
                    y={Number(y) + Number(height) / 2}
                    fill="#fff"
                    style={{ writingMode: "sideways-lr" }}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    className="text-xs md:text-sm lg:text-lg"
                  >
                    {short}
                  </text>
                </g>
              );
            }}
          />
          <LabelList
            dataKey={countDataKey}
            position="top"
            offset={4}
            className="md:text-md fill-foreground text-xs"
          />
        </Bar>
      </RechartBarChart>
    </ChartContainer>
  );
};

export default BarChart;
