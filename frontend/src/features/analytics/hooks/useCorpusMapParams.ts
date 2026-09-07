import { parseAsString, parseAsStringEnum, useQueryStates } from "nuqs";

export const useCorpusMapParams = () => {
  return useQueryStates({
    tab: parseAsStringEnum(["list", "chart"])
      .withDefault("chart")
      .withOptions({ clearOnDefault: true }),
    search: parseAsString.withDefault("").withOptions({ clearOnDefault: true }),
    topicId: parseAsString
      .withDefault("")
      .withOptions({ clearOnDefault: true }),
    conceptId: parseAsString
      .withDefault("")
      .withOptions({ clearOnDefault: true }),
  });
};
