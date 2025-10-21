"use client";
import {
  parseAsArrayOf,
  parseAsString,
  parseAsStringEnum,
  useQueryState,
  type UseQueryStateReturn,
} from "nuqs";

export const useTagSearchParams = (
  defaultValues: string[],
): UseQueryStateReturn<string[], string[]> => {
  const [tags, setTags] = useQueryState(
    "tags",
    parseAsArrayOf(parseAsStringEnum(defaultValues), ",")
      .withDefault(defaultValues)
      .withOptions({ clearOnDefault: true }),
  );

  return [tags, setTags];
};
