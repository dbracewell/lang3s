import { parseAsString, parseAsStringEnum, useQueryStates } from "nuqs";
import { parseAsInteger } from "nuqs/server";

export const useCohortsParams = () => {
  return useQueryStates({
    tab: parseAsStringEnum(["list", "chart"])
      .withDefault("list")
      .withOptions({ clearOnDefault: true }),
    q: parseAsString.withDefault("").withOptions({ clearOnDefault: true }),
    c: parseAsInteger.withDefault(-1).withOptions({ clearOnDefault: true }),
  });
};
