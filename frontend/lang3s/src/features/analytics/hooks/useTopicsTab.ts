import { parseAsStringEnum, useQueryState } from "nuqs";

export const useTopicsTab = () => {
  return useQueryState(
    "tab",
    parseAsStringEnum(["list", "chart"])
      .withDefault("list")
      .withOptions({ clearOnDefault: true }),
  );
};
