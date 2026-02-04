import z from "zod";
import { Chart, CountType, SERIES_SOURCES } from "@/features/reports/types";

export const SeriesSchema = z.object({
  type: z.enum(SERIES_SOURCES),
  value: z.string(),
});

export type SeriesType = z.infer<typeof SeriesSchema>;

export const ChartSchema = z.object({
  x: SeriesSchema,
  y: SeriesSchema.optional(),
  count: z.enum(Chart.countTypes).refine((a) => a as CountType),
});

export type ChartSchemaType = z.infer<typeof ChartSchema>;
