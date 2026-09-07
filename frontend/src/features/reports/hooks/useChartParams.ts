import { parseAsString, parseAsStringEnum, useQueryStates } from "nuqs";
import { parsePageIndex } from "@/lib/parsers";
import { SERIES_SOURCES } from "@/features/reports/types";

export const useChartParams = () => {
  return useQueryStates({
    xPage: parsePageIndex.withDefault(1).withOptions({ clearOnDefault: true }),
    yPage: parsePageIndex.withDefault(1).withOptions({ clearOnDefault: true }),
    xType: parseAsStringEnum([...SERIES_SOURCES])
      .withDefault("TOPIC")
      .withOptions({ clearOnDefault: true }),
    yType: parseAsStringEnum([...SERIES_SOURCES, ""])
      .withDefault("")
      .withOptions({ clearOnDefault: true }),
    xValue: parseAsString.withDefault("").withOptions({ clearOnDefault: true }),
    yValue: parseAsString.withDefault("").withOptions({ clearOnDefault: true }),
    count: parseAsStringEnum(["mention", "sentence", "document"]).withOptions({
      clearOnDefault: true,
    }),
  });
};
