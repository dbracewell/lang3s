import { ChartSchemaType } from "@/features/reports/schema";
import { useTRPCQuery } from "@/lib/trpc/use-queries";
import { Spinner } from "@/components/Spinner";
import BarChart from "@/features/reports/ui/components/BarChart";
import { HeatMap } from "@/features/reports/ui/components/HeatMap";

import { LineChart } from "@/features/reports/ui/components/LineChart";
import { ScatterPlotChart } from "@/features/reports/ui/components/ScatterPlot";
import { Chart } from "@/features/reports/types";

export const ChartView = ({ chart }: { chart: ChartSchemaType }) => {
  const { data, isPending, isError, error } = useTRPCQuery((trpc) =>
    trpc.reports.getData.queryOptions({ ...chart }),
  );

  if (isError) {
    throw new Error(error?.message);
  }

  if (isPending || data == null) {
    return <Spinner />;
  }

  const chartType = Chart.getChartType(chart.x.dataType, chart.y?.dataType);

  switch (chartType) {
    case "heatmap":
      return <HeatMap data={data} countType={chart.count} />;
    case "linechart":
      return (
        <LineChart
          data={data}
          countType={chart.count}
          xSeries={chart.x}
          ySeries={chart.y!}
        />
      );
    case "scatterplot":
      return (
        <ScatterPlotChart
          data={data}
          countType={chart.count}
          xSeries={chart.x}
          ySeries={chart.y!}
        />
      );
    case "barchart":
      return (
        <BarChart
          xAxisType={chart.x.type}
          xAxisValue={chart.x.value ?? ""}
          countType={chart.count}
          data={data}
        />
      );
  }
};
