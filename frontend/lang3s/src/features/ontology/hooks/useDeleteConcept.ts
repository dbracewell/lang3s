import { useCallback } from "react";
import { useTRPCMutation } from "@/lib/trpc/use-mutation";
import { toast } from "sonner";
import { useConfirmationDialog } from "@/components/dialogs/ConfirmationDialog";

export const useDeleteConcept = () => {
  const { mutate, isPending } = useTRPCMutation((trpc) => ({
    mutation: trpc.ontology.deleteConcept.mutationOptions({
      onSuccess: (data) =>
        toast.success(`Successfully deleted ${data.name} and all children`),
      onError: () => toast.error("Failed to delete concept"),
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
