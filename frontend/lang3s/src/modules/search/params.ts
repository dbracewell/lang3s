import {
  parseAsBoolean,
  parseAsFloat,
  parseAsInteger,
  parseAsString,
  parseAsStringEnum,
} from "nuqs/server";
import { z } from "zod";

export const QueryTypes = ["document", "annotation", "sentence"];

export const Lang3sSearchParams = {
  q: parseAsString.withDefault("").withOptions({ clearOnDefault: true }),
  aid: parseAsString.withDefault("").withOptions({ clearOnDefault: true }),
  atype: parseAsString.withDefault("").withOptions({ clearOnDefault: true }),
  minSimilarity: parseAsFloat
    .withDefault(0.6)
    .withOptions({ clearOnDefault: true }),
  page: parseAsInteger.withDefault(1).withOptions({ clearOnDefault: true }),
  stype: parseAsStringEnum(QueryTypes)
    .withDefault("document")
    .withOptions({ clearOnDefault: true }),
  semantic: parseAsBoolean
    .withDefault(false)
    .withOptions({ clearOnDefault: true }),
};

export const SearchParamSchema = z.object({
  q: z.string().nullish(),
  aid: z.string().nullish(),
  atype: z.string().nullish(),
  page: z.number().int().min(1).default(1).nullish(),
  stype: z.enum(QueryTypes).default("document").nullish(),
  minSimilarity: z.number().min(0).max(1.0).default(0.6).nullish(),
  semantic: z.boolean().default(false).nullish(),
});

export type ParsedSearchParams = z.infer<typeof SearchParamSchema>;
