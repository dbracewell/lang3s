"use server";
import { postJson } from "@/lib/utils/superFetch";
import { ChartType, CountType } from "@/features/reports/types";
import { DataTypeCategory } from "@/features/common/types";
import { ChartSeriesParamType } from "@/features/reports/schema";
import { DataType } from "@/lib/db/schemas/metadata";

const BASE_PATH = `${process.env.EMBEDDING_SERVER}/charts`;

export type ChartData = {
  text1: string;
  text2: string;
  value1: string | number;
  value2: string | number;
  documentCount: number;
  sentenceCount: number;
  mentionCount: number;
};

export type ChartResult = {
  x_total: number;
  y_total: number;
  x_data_type: DataTypeCategory;
  y_data_type: DataTypeCategory | null;
  x_next_page: number | null;
  y_next_page: number | null;
  x_prev_page: number | null;
  y_prev_page: number | null;
  chart_type: ChartType;
  results: ChartData[];
};

type ChartApiSeries = ChartSeriesParamType & {
  page_size: number;
  data_type: DataType;
  formatter: string | null;
};

type ChartApiRequest = {
  chart_type: ChartType;
  count_type: CountType;
  x: ChartApiSeries;
  y?: ChartApiSeries;
};

export const getChartData = async (chartData: ChartApiRequest) => {
  return postJson<ChartResult>(`${BASE_PATH}`, {
    ...chartData,
  });
};
