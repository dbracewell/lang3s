import { useCallback } from "react";
import { toast } from "sonner";
import { useConfirmationDialog } from "@/components/dialogs/ConfirmationDialog";
import { useMutation } from "@tanstack/react-query";
import { coreClient } from "@/lib/api";
import { deleteOntologyEntryMutation } from "@/clients/core/@tanstack/react-query.gen";

export const useDeleteConcept = () => {
  const { mutate, isPending } = useMutation({
    ...deleteOntologyEntryMutation({
      client: coreClient,
    }),
    onSuccess: () =>
      toast.success(`Successfully deleted concept and all children`),
    onError: () => toast.error("Failed to delete concept"),
  });

  const { confirm, Dialog } = useConfirmationDialog({
    title: "Are you sure you want to delete this concept?",
    description:
      "This will delete all child concepts as well and cannot be undone.",
    confirmVariant: "destructive",
  });

  const mutateFn = useCallback(
    async (id: number) => {
      const response = await confirm();
      if (response) {
        mutate({
          path: {
            node_id: id,
          },
        });
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
