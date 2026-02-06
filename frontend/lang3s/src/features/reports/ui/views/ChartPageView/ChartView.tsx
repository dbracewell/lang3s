"use client";
import { useTRPCQuery } from "@/lib/trpc/use-queries";
import { Spinner } from "@/components/Spinner";
import { HeatMap } from "@/features/reports/ui/components/HeatMap";
import { useChartParams } from "@/features/reports/hooks/useChartParams";
import { ScatterPlotChart } from "@/features/reports/ui/components/ScatterPlot";
import { LineChart } from "@/features/reports/ui/components/LineChart";
import BarChart from "@/features/reports/ui/components/BarChart";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { getChartTypeTitle } from "@/features/reports/types";
import { capitalize, formatURL } from "@/lib/utils/formatters";
import { Button } from "@/components/ui/button";
import {
  ChevronDownIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ChevronUpIcon,
  FileImageIcon,
  XIcon,
} from "lucide-react";
import { useRef, useState } from "react";
import { useSvgExport } from "@/features/common/hooks/useSvgExport";
import { useTheme } from "next-themes";
import { ChartSeriesParamType } from "@/features/reports/schema";
import { useRouter } from "next/navigation";

export const ChartView = () => {
  const [params, setParams] = useChartParams();
  const [xPage, setXPage] = useState(params.xPage);
  const [yPage, setYPage] = useState(params.yPage);
  const countType = params.count ?? "document";
  const xAxis = {
    type: params.xType,
    value: params.xValue,
    page: xPage,
  } as ChartSeriesParamType;
  const yAxis = params.yType
    ? ({
        type: params.yType,
        value: params.yValue,
        page: yPage,
      } as ChartSeriesParamType)
    : undefined;

  const { data, isPending } = useTRPCQuery((trpc) =>
    trpc.reports.getData.queryOptions(
      {
        count_type: countType,
        x: xAxis,
        y: yAxis,
      },
      { placeholderData: (previousData) => previousData },
    ),
  );

  const contentRef = useRef<HTMLDivElement | null>(null);
  const { exportSvg } = useSvgExport();
  const { theme } = useTheme();
  const router = useRouter();

  if (isPending || data == null) {
    return <Spinner />;
  }

  const chartType = data.chart_type;

  const saveSvg = async () => {
    if (!contentRef.current) return;
    const lightMode = "#fafafa";
    const darkMode = "#171717";
    const svgRef = contentRef.current.querySelector("svg");
    await exportSvg(svgRef, {
      filename: `${chartType}-${Date.now()}.png`,
      backgroundColor: theme === "dark" ? darkMode : lightMode,
      scale: 3,
    });
  };

  const getChart = () => {
    switch (chartType) {
      case "heatmap":
        return <HeatMap data={data.results} countType={countType} />;
      case "linechart":
        return (
          <LineChart
            className="w-full"
            xDataType={data.x_data_type}
            data={data.results}
            countType={countType}
            xSeries={xAxis}
            ySeries={yAxis}
          />
        );
      case "scatterplot":
        return (
          <ScatterPlotChart
            className="w-full"
            data={data.results}
            countType={countType}
            xSeries={xAxis}
            ySeries={yAxis!}
            xDataType={data.x_data_type}
            yDataType={data.y_data_type!}
          />
        );
      case "barchart":
        return (
          <BarChart
            xAxisType={params.xType}
            xAxisValue={params.xValue ?? ""}
            countType={countType}
            data={data.results}
            className="w-full"
          />
        );
    }
  };

  return (
    <div className="animate-in flex h-full flex-1 overflow-hidden">
      <Card className="m-1 flex min-h-0 flex-1 flex-col">
        <CardHeader>
          <CardTitle className="text-3xl">
            <span className="text-dodger-blue-500 mr-2">
              {capitalize(xAxis.type, true)}
            </span>
            <span className="text-muted-foreground mr-2">
              {yAxis?.type && (
                <>
                  by{" "}
                  <span className="text-dodger-blue-500">
                    {capitalize(yAxis.type, true)}
                  </span>
                </>
              )}
            </span>
            <span className="text-muted-foreground">
              {getChartTypeTitle(chartType)}
            </span>
          </CardTitle>
          <CardDescription>
            <span className="mr-2">
              {yAxis && xAxis && "X-axis = "}
              {xAxis.value}
            </span>
            <span>{yAxis?.value && `Y-axis = ${yAxis.value}`}</span>
          </CardDescription>
          <CardAction className="flex items-center gap-4">
            <Button onClick={saveSvg} variant="listButton">
              <FileImageIcon />
            </Button>
            <Button
              variant="ghost"
              onClick={() =>
                router.push(
                  formatURL("/reports/charts", {
                    ...params,
                    xPage: 1,
                    yPage: 1,
                  }),
                )
              }
            >
              <XIcon />
            </Button>
          </CardAction>
        </CardHeader>
        <CardContent
          className="flex h-full min-h-0 w-full flex-1 flex-col"
          ref={contentRef}
        >
          <div className="flex h-[calc(100%-40px)] flex-1 gap-4">
            <div className="flex flex-col justify-between">
              <Button
                variant="ghost"
                disabled={!data.y_prev_page}
                style={{
                  writingMode: "vertical-rl",
                }}
                className="h-fit!"
                onClick={() => {
                  setYPage(data.y_prev_page ?? 1);
                  setParams(
                    {
                      yPage: data.y_prev_page,
                    },
                    {
                      shallow: true,
                    },
                  );
                }}
              >
                <ChevronUpIcon /> Previous Page
              </Button>
              <Button
                disabled={!data.y_next_page}
                variant="ghost"
                style={{
                  writingMode: "vertical-rl",
                }}
                className="h-fit!"
                onClick={() => {
                  setYPage(data.y_next_page ?? 1);
                  setParams(
                    {
                      yPage: data.y_next_page,
                    },
                    {
                      shallow: true,
                    },
                  );
                }}
              >
                Next Page
                <ChevronDownIcon />
              </Button>
            </div>
            <div className="flex w-[calc(100%-100px)] flex-1">{getChart()}</div>
          </div>
          <div className="ml-20 flex items-center justify-between">
            <Button
              disabled={!data.x_prev_page}
              variant="ghost"
              onClick={() => {
                setXPage(data.x_prev_page ?? 1);
                setParams(
                  {
                    xPage: data.x_prev_page,
                  },
                  {
                    shallow: true,
                  },
                );
              }}
            >
              <ChevronLeftIcon /> Previous Page
            </Button>
            <Button
              disabled={!data.x_next_page}
              variant="ghost"
              onClick={() => {
                setXPage(data.x_next_page ?? 1);
                setParams(
                  {
                    xPage: data.x_next_page,
                  },
                  {
                    shallow: true,
                  },
                );
              }}
            >
              Next Page <ChevronRightIcon />
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
