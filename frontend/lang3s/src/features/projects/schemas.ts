import z from "zod";
import { SearchParamSchema } from "@/features/search/schemas";

export const CreateProjectSchema = z.object({
  name: z.string().min(1, "Project name is required"),
  description: z.string().min(2, "Project description is required"),
});

export const ProjectSchema = CreateProjectSchema.extend({
  dataParams: SearchParamSchema,
});

export type ProjectSchemaType = z.infer<typeof ProjectSchema>;
