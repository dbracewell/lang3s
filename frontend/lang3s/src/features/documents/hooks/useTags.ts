import { parseAsArrayOf, parseAsString, useQueryState } from "nuqs";
import { ONTOLOGY_ENTITY_ROOT } from "@/features/common/constants";

export const useTags = () => {
  return useQueryState(
    "tags",
    parseAsArrayOf(parseAsString)
      .withDefault([ONTOLOGY_ENTITY_ROOT])
      .withOptions({ clearOnDefault: true }),
  );
};
