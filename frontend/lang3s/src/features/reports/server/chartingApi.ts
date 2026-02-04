"use server";
import { postJson } from "@/lib/utils/superFetch";
import { ChartType } from "@/features/reports/types";
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
  x_next_page: number | null;
  y_next_page: number | null;
  x_prev_page: number | null;
  y_prev_page: number | null;
  chart_type: ChartType;
  results: ChartData[];
};

type SeriesInformation = {
  type: string;
  value: string;
  page: number;
  page_size: number;
  data_type: DataType;
  formatter: string | undefined;
};

export type ChartDataRequest = {
  chart_type: ChartType;
  x: SeriesInformation;
  y?: SeriesInformation;
  count_type: "document" | "sentence" | "mention";
};

export const getChartData = async (chartData: ChartDataRequest) => {
  return postJson<ChartResult>(`${BASE_PATH}`, {
    ...chartData,
  });
};
