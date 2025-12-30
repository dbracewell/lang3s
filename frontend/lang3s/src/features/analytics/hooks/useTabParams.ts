import { parseAsStringEnum, useQueryState } from "nuqs";

export const useTabParams = () => {
  return useQueryState(
    "tab",
    parseAsStringEnum(["list", "chart"])
      .withDefault("list")
      .withOptions({ clearOnDefault: true }),
  );
};
