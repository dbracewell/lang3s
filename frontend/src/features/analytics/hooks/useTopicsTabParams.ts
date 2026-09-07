import { parseAsStringEnum, useQueryState } from "nuqs";

export const useTopicsTabParams = () => {
  return useQueryState(
    "tab",
    parseAsStringEnum(["list", "chart"])
      .withDefault("list")
      .withOptions({ clearOnDefault: true }),
  );
};
