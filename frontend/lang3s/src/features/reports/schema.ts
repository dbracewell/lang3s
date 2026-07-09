import z from "zod";
import { SERIES_SOURCES } from "@/features/reports/types";
import { CountType } from "@/clients/analytics";
import { zCountType } from "@/clients/analytics/zod.gen";

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
  count: zCountType.refine((a) => a as CountType),
});

export type ChartFormType = z.infer<typeof ChartFormSchema>;
