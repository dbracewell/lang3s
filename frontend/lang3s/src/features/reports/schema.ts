import z from "zod";
import {
  Chart,
  CountType,
  DisplayType,
  SeriesSourceType,
} from "@/features/reports/types";
import { DataTypeCategory } from "@/features/common/types";

export const SeriesSchema = z.discriminatedUnion("type", [
  z.object({
    type: z.literal("TOPIC").refine((a) => a as SeriesSourceType),
    value: z.string().optional(),
    dataType: z.literal("string").refine((a) => a as DataTypeCategory),
    display: z.enum(["text"]).refine((a) => a as DisplayType),
  }),
  z.object({
    type: z
      .enum(["DOCUMENT_METADATA", "SENTENCE_METADATA", "ANNOTATION_METADATA"])
      .refine((a) => a as SeriesSourceType),
    value: z.string(),
    dataType: z
      .enum(["string", "number", "date", "boolean"])
      .refine((a) => a as DataTypeCategory),
    display: z.enum(["value"]).refine((a) => a as DisplayType),
  }),
  z.object({
    type: z.literal("ANNOTATION").refine((a) => a as SeriesSourceType),
    value: z.string(),
    dataType: z.literal("string").refine((a) => a as DataTypeCategory),
    display: z
      .enum(["text", "value", "text-value"])
      .refine((a) => a as DisplayType),
  }),
]);

export type SeriesType = z.infer<typeof SeriesSchema>;

export const ChartSchema = z.object({
  x: SeriesSchema,
  y: SeriesSchema.optional(),
  count: z.enum(Chart.countTypes).refine((a) => a as CountType),
});

export type ChartSchemaType = z.infer<typeof ChartSchema>;
