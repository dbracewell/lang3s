import { z } from "zod";

export const SearchParamSchema = z.object({
  q: z.string().trim().nullish(),
  aid: z.array(z.string().trim()).nullish(),
  sid: z.array(z.string().trim()).nullish(),
  tid: z.array(z.string().trim()).nullish(),
  cursor: z.number().int().min(1).default(1).nullish(),
  isStrict: z.boolean().default(true).nullish(),
});

export type ParsedSearchParams = z.infer<typeof SearchParamSchema>;
