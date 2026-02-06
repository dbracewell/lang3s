import z from "zod";
import { Chart, CountType, SERIES_SOURCES } from "@/features/reports/types";

export const NoValueSeriesSchema = z.object({
  type: z.literal("TOPIC"),
  value: z.string(),
});
export const HasValueSeriesSchema = z.object({
  type: z.enum([...SERIES_SOURCES.filter((s) => s != "TOPIC")]),
  value: z.string().min(1),
});

export const SeriesFormSchema = z.discriminatedUnion("type", [
  NoValueSeriesSchema,
  HasValueSeriesSchema,
]);
export type SeriesFormType = z.infer<typeof SeriesFormSchema>;

export const ChartFormSchema = z.object({
  x: SeriesFormSchema,
  y: SeriesFormSchema.optional(),
  count: z.enum(Chart.countTypes).refine((a) => a as CountType),
});

export type ChartFormType = z.infer<typeof ChartFormSchema>;

export const ChartSeriesParamsSchema = z.object({
  type: z.enum(SERIES_SOURCES),
  value: z.string(),
  page: z.int().optional(),
});

export type ChartSeriesParamType = z.infer<typeof ChartSeriesParamsSchema>;

export const ChartParamsSchema = z.object({
  x: ChartSeriesParamsSchema,
  y: ChartSeriesParamsSchema.optional(),
  count_type: z.enum(Chart.countTypes),
});
