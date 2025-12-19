import {
  parseAsBoolean,
  parseAsInteger,
  parseAsString,
  parseAsStringEnum,
} from "nuqs/server";
import { z } from "zod";

export const QueryTypes = ["document", "annotation", "sentence"] as const;

export type Lang3sQueryType = (typeof QueryTypes)[number];

export const Lang3sSearchParams = {
  q: parseAsString.withDefault("").withOptions({ clearOnDefault: true }),
  aid: parseAsString.withDefault("").withOptions({ clearOnDefault: true }),
  atype: parseAsString.withDefault("").withOptions({ clearOnDefault: true }),
  cursor: parseAsInteger.withDefault(1).withOptions({ clearOnDefault: true }),
  stype: parseAsStringEnum([...QueryTypes])
    .withDefault("document")
    .withOptions({ clearOnDefault: true }),
  isStrict: parseAsBoolean
    .withDefault(true)
    .withOptions({ clearOnDefault: true }),
};

export const SearchParamSchema = z.object({
  q: z.string().nullish(),
  aid: z.string().nullish(),
  atype: z.string().nullish(),
  cursor: z.number().int().min(1).default(1).nullish(),
  stype: z.enum(QueryTypes).default("document").nullish(),
  isStrict: z.boolean().default(true).nullish(),
});

export type ParsedSearchParams = z.infer<typeof SearchParamSchema>;
