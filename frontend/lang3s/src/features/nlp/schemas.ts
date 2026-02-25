import z from "zod";

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

export const Lang3sFile = z.object({
  path: z.string().nullish(),
  docId: z.string().nullish(),
  mime_type: z.string(),
  content: z.string(),
  encoding: z.string().nullish(),
  metadata: z.record(z.string(), z.any()).default({}).optional(),
});
