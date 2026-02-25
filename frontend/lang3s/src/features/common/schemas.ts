import z from "zod";

import {
  DataType,
  DataTypeNames,
  MetadataSource,
  MetadataSources,
} from "@/lib/db/schemas/metadata";

export const MetadataSchema = z.object({
  name: z.string().min(1, "Metadata name is required"),
  dataType: z.enum(DataTypeNames).refine((a) => a as DataType),
  source: z.enum(MetadataSources).refine((a) => a as MetadataSource),
  formatter: z.string().optional(),
});

export type MetadataSchemaType = z.infer<typeof MetadataSchema>;
