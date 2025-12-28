import {
  parseAsArrayOf,
  parseAsStringEnum,
  useQueryState,
  type UseQueryStateReturn,
} from "nuqs";

export const defaultValues = [
  "ALL.Entity.Physical",
  "ALL.Entity.Abstract.Social_And_Collective",
];

export const useTagSearchParams = (
  values: string[],
): UseQueryStateReturn<string[], string[]> => {
  const [tags, setTags] = useQueryState(
    "tags",
    parseAsArrayOf(parseAsStringEnum(values), ",")
      .withDefault(defaultValues)
      .withOptions({ clearOnDefault: true }),
  );

  return [tags, setTags];
};
