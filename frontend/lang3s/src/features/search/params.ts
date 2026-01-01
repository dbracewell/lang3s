import {
  parseAsArrayOf,
  parseAsBoolean,
  parseAsInteger,
  parseAsString,
  parseAsStringEnum,
} from "nuqs/server";
import { z } from "zod";

export const Lang3sSearchParams = {
  q: parseAsString.withDefault("").withOptions({ clearOnDefault: true }),
  aid: parseAsArrayOf(parseAsString, ",")
    .withDefault([])
    .withOptions({ clearOnDefault: true }),
  sid: parseAsArrayOf(parseAsString, ",")
    .withDefault([])
    .withOptions({ clearOnDefault: true }),
  tid: parseAsArrayOf(parseAsString, ",")
    .withDefault([])
    .withOptions({ clearOnDefault: true }),
  cursor: parseAsInteger.withDefault(1).withOptions({ clearOnDefault: true }),
  isStrict: parseAsBoolean
    .withDefault(true)
    .withOptions({ clearOnDefault: true }),
  tab: parseAsStringEnum(["docs", "annotations", "topics"])
    .withDefault("docs")
    .withOptions({ clearOnDefault: true }),
  placeholder: parseAsString
    .withDefault("")
    .withOptions({ clearOnDefault: true }),
};

export const SearchParamSchema = z.object({
  q: z.string().trim().nullish(),
  aid: z.array(z.string().trim()).nullish(),
  sid: z.array(z.string().trim()).nullish(),
  tid: z.array(z.string().trim()).nullish(),
  cursor: z.number().int().min(1).default(1).nullish(),
  isStrict: z.boolean().default(true).nullish(),
});

export type ParsedSearchParams = z.infer<typeof SearchParamSchema>;
