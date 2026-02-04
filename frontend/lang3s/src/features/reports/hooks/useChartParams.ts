import { parseAsString, parseAsStringEnum, useQueryStates } from "nuqs";
import { parsePageIndex } from "@/lib/parsers";
import { SERIES_SOURCES } from "@/features/reports/types";
import { DataTypeNames } from "@/lib/db/schemas/metadata";

export const useChartParams = () => {
  return useQueryStates({
    xPage: parsePageIndex.withDefault(1).withOptions({ clearOnDefault: true }),
    yPage: parsePageIndex.withDefault(1).withOptions({ clearOnDefault: true }),
    xType: parseAsStringEnum([...SERIES_SOURCES])
      .withDefault("TOPIC")
      .withOptions({ clearOnDefault: true }),
    yType: parseAsStringEnum([...SERIES_SOURCES])
      .withDefault("TOPIC")
      .withOptions({ clearOnDefault: true }),
    xValue: parseAsString.withDefault("").withOptions({ clearOnDefault: true }),
    yValue: parseAsString.withDefault("").withOptions({ clearOnDefault: true }),
    xDataType: parseAsStringEnum([...DataTypeNames])
      .withDefault("string")
      .withOptions({ clearOnDefault: true }),
    yDataType: parseAsStringEnum([...DataTypeNames])
      .withDefault("string")
      .withOptions({ clearOnDefault: true }),
    view: parseAsStringEnum(["form", "chart"])
      .withDefault("form")
      .withOptions({ clearOnDefault: true }),
  });
};
