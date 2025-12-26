import { useTRPCQuery } from "@/lib/trpc/use-queries";
import { useCallback, useMemo } from "react";
import { DEFAULT_ONTOLOGY_COLOR } from "@/features/ontology/constants";
import { useTRPCMutation } from "@/lib/trpc/use-mutation";
import { toast } from "sonner";
import { useConfirmationDialog } from "@/components/ConfirmationDialog";

export const useUpdateOntology = () => {
  return useTRPCMutation((trpc) => ({
    mutation: trpc.ontology.updateConcept.mutationOptions(),
    successToast: "Successfully updated ontology",
    errorToast: "Failed to update ontology",
  }));
};

export const useAddConcept = () => {
  return useTRPCMutation((trpc) => ({
    mutation: trpc.ontology.addConcept.mutationOptions({
      onSuccess: (data) =>
        toast.success(`Successfully created ${data[0].name}`),
      onError: () => toast.error("Failed to create new concept"),
    }),
  }));
};

export const useDeleteConcept = () => {
  const { mutate, isPending } = useTRPCMutation((trpc) => ({
    mutation: trpc.ontology.deleteConcept.mutationOptions({
      onSuccess: (data) =>
        toast.success(
          `Successfully deleted ${data.name} and all it's children`,
        ),
      onError: () => toast.error("Failed to delete  concept"),
    }),
  }));

  const { confirm, Dialog } = useConfirmationDialog({
    title: "Are you sure you want to delete this concept?",
    description:
      "This will delete all child concepts as well and cannot be undone.",
    confirmVariant: "destructive",
  });

  const mutateFn = useCallback(
    async (path: string) => {
      const response = await confirm();
      if (response) {
        mutate({ path });
      }
    },
    [confirm, mutate],
  );

  return {
    mutateFn,
    Dialog,
    isPending,
  };
};

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
