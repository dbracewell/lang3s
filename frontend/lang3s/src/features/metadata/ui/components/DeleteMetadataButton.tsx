"use client";
import { useConfirmationDialog } from "@/components/dialogs/ConfirmationDialog";
import { Trash2Icon } from "lucide-react";
import { useTRPCMutation } from "@/lib/trpc/use-mutation";
import { useRouter } from "next/navigation";
import { LoadingButton } from "@/components/ui/loading-button";

export const DeleteMetadataButton = ({
  name,
  id,
}: {
  name: string;
  id: string;
}) => {
  const { Dialog, confirm } = useConfirmationDialog({
    title: `Are you sure you want to delete ${name}`,
    description: "This operation cannot be undone",
    confirmVariant: "destructive",
  });
  const router = useRouter();
  const deleteMetadata = useTRPCMutation((trpc) => ({
    mutation: trpc.system.deleteMetadata.mutationOptions({
      onSuccess: () => router.refresh(),
    }),
    successToast: `Successfully deleted ${name}`,
    errorToast: `Failed to delete ${name}`,
  }));

  const onClick = async () => {
    const response = await confirm();
    if (response) {
      deleteMetadata.mutate({ id });
    }
  };

  return (
    <>
      <Dialog />
      <LoadingButton
        type="button"
        isLoading={deleteMetadata.isPending}
        variant="ghost"
        className="hover:bg-destructive dark:hover:bg-destructive hover:text-white"
        size="icon-sm"
        onClick={onClick}
      >
        <Trash2Icon />
      </LoadingButton>
    </>
  );
};
