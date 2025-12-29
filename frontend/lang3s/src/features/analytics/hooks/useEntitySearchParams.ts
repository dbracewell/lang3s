import {
  parseAsArrayOf,
  parseAsBoolean,
  parseAsString,
  parseAsStringEnum,
  useQueryStates,
} from "nuqs";
import { parsePageIndex } from "@/features/common/lib/parsers";

export const defaultValues = [
  "ALL.Entity.Physical",
  "ALL.Entity.Abstract.Social_And_Collective",
];

type EntitySearchParams = {
  page: number;
  sortBy: string;
  filter: string;
  tags: string[];
  entity: string;
  entityType: string;
  showEvents: boolean;
};

export const useEntitySearchParams = (values: string[]) => {
  const queryStates = useQueryStates({
    page: parsePageIndex.withDefault(1).withOptions({ clearOnDefault: true }),
    sortBy: parseAsStringEnum(["mentions", "docs", "mentionsPerDoc"])
      .withDefault("mentions")
      .withOptions({ clearOnDefault: true }),
    filter: parseAsString.withDefault("").withOptions({ clearOnDefault: true }),
    tags: parseAsArrayOf(parseAsStringEnum(values), ",")
      .withDefault(defaultValues)
      .withOptions({ clearOnDefault: true }),
    entity: parseAsString.withDefault("").withOptions({ clearOnDefault: true }),
    entityType: parseAsString
      .withDefault("")
      .withOptions({ clearOnDefault: true }),
    showEvents: parseAsBoolean
      .withDefault(false)
      .withOptions({ clearOnDefault: true }),
  });
  return queryStates;
};
