import { parsePageIndex } from "@/features/common/lib/parsers";
import {
  parseAsArrayOf,
  parseAsBoolean,
  parseAsString,
  parseAsStringEnum,
} from "nuqs/server";

export const defaultValues = [
  "ALL.Entity.Physical",
  "ALL.Entity.Abstract.Social_And_Collective",
];

export const entitySearchParams = {
  page: parsePageIndex.withDefault(1).withOptions({ clearOnDefault: true }),
  sortBy: parseAsStringEnum(["mentions", "docs", "mentionsPerDoc"])
    .withDefault("mentions")
    .withOptions({ clearOnDefault: true }),
  filter: parseAsString.withDefault("").withOptions({ clearOnDefault: true }),
  tags: parseAsArrayOf(parseAsString, ",")
    .withDefault(defaultValues)
    .withOptions({ clearOnDefault: true }),
  entity: parseAsString.withDefault("").withOptions({ clearOnDefault: true }),
  entityType: parseAsString
    .withDefault("")
    .withOptions({ clearOnDefault: true }),
  showEvents: parseAsBoolean
    .withDefault(false)
    .withOptions({ clearOnDefault: true }),
};
