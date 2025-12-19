import { useTRPCQuery } from "@/lib/trpc/use-queries";
import { useCallback, useMemo } from "react";
import { DEFAULT_ONTOLOGY_COLOR } from "@/features/ontology/constants";

export const useOntologyColors = () => {
  const { data, isPending } = useTRPCQuery((trpc) =>
    trpc.ontology.getColorMapping.queryOptions(undefined, {
      staleTime: 24 * 60 * 60 * 1000,
    }),
  );

  const activeColors = useMemo(() => {
    const activeColors: Record<string, string> = {
      LOC: "GREEN",
      MISC: "RED",
      ORG: "BLUE",
      DATE: "YELLOW",
      CARDINAL: "GRAY",
      PERSON: "PURPLE",
    };

    return activeColors;
  }, [data, isPending]);

  const getOntologyColor = useCallback(
    (name: string) => activeColors[name] ?? DEFAULT_ONTOLOGY_COLOR,
    [activeColors],
  );

  return { getOntologyColor };
};
