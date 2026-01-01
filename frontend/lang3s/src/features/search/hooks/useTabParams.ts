import { parseAsStringEnum, useQueryState } from "nuqs";

export const useTabParams = (shallow: boolean = true) => {
  return useQueryState(
    "tab",
    parseAsStringEnum(["docs", "annotations", "topics"])
      .withDefault("docs")
      .withOptions({ clearOnDefault: true, shallow }),
  );
};
