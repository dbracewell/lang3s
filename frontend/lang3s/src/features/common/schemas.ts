import z from "zod";
import {
  DATA_TYPES,
  DataType,
  METADATA_SOURCES,
  MetadataSourceType,
} from "@/features/common/types";

export const MetadataSchema = z.object({
  name: z.string().min(1, "Metadata name is required"),
  dataType: z.enum(DATA_TYPES).refine((a) => a as DataType),
  source: z.enum(METADATA_SOURCES).refine((a) => a as MetadataSourceType),
  formatter: z.string().optional(),
});

export type MetadataSchemaType = z.infer<typeof MetadataSchema>;

export const TextAnnotationSchema = z.object({
  id: z.string(),
  text: z.string(),
  metadata: z.record(z.string(), z.any()),
  embedding: z.array(z.number()),
  start: z.int(),
  end: z.int(),
  type: z.string(),
  value: z.string(),
  sentence_id: z.int(),
});

export const TextSchema = z.object({
  id: z.string(),
  text: z.string(),
  metadata: z.record(z.string(), z.any()),
  embedding: z.array(z.number()),
  annotations: z.array(TextAnnotationSchema),
});

export const DocumentSchema = z.object({
  id: z.string(),
  title: z.string(),
  metadata: z.record(z.string(), z.any()),
  text: TextSchema,
});
