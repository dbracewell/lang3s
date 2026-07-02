import z from "zod";
import { DataType, MetadataSource } from "@/clients/core";

export const DataTypeNames = [
  "string",
  "string_array",
  "int",
  "float",
  "boolean",
  "date",
] as const;

export const MetadataSources = ["document", "annotation", "sentence"];

export const MetadataSchema = z.object({
  name: z.string().min(1, "Metadata name is required"),
  dataType: z.enum(DataTypeNames).refine((a) => a as DataType),
  source: z.enum(MetadataSources).refine((a) => a as MetadataSource),
  formatter: z.string().optional(),
});

export type MetadataSchemaType = z.infer<typeof MetadataSchema>;
