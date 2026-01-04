import {
  parseAsArrayOf,
  parseAsBoolean,
  parseAsInteger,
  parseAsString,
  parseAsStringEnum,
  useQueryStates,
} from "nuqs";

export const useGlobalSearchParams = () => {
  return useQueryStates({
    q: parseAsString.withDefault("").withOptions({ clearOnDefault: true }),
    aid: parseAsArrayOf(parseAsString, ",")
      .withDefault([])
      .withOptions({ clearOnDefault: true }),
    sid: parseAsArrayOf(parseAsString, ",")
      .withDefault([])
      .withOptions({ clearOnDefault: true }),
    tid: parseAsArrayOf(parseAsString, ",")
      .withDefault([])
      .withOptions({ clearOnDefault: true }),
    cursor: parseAsInteger.withDefault(1).withOptions({ clearOnDefault: true }),
    isStrict: parseAsBoolean
      .withDefault(true)
      .withOptions({ clearOnDefault: true }),
    tab: parseAsStringEnum(["docs", "annotations", "topics"])
      .withDefault("docs")
      .withOptions({ clearOnDefault: true }),
    placeholder: parseAsString
      .withDefault("")
      .withOptions({ clearOnDefault: true }),
  });
};
