"use client";
import { useConfirmationDialog } from "@/components/dialogs/ConfirmationDialog";
import { LoadingButton } from "@/components/ui/loading-button";
import { useTRPCMutation } from "@/lib/trpc/use-mutation";
import { UserX2Icon } from "lucide-react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

export const DeleteUser = ({ userId }: { userId: string }) => {
  const router = useRouter();
  const { isPending, mutate } = useTRPCMutation((trpc) => ({
    mutation: trpc.auth.deleteUser.mutationOptions({
      onSuccess: (data) => {
        if (data) {
          toast.success("Successfully removed user");
          router.replace("/admin/users");
          return;
        } else {
          toast.error("Failed to delete user");
        }
      },
    }),
  }));
  const { confirm, Dialog } = useConfirmationDialog({
    title: "Delete user",
    description: "This action cannot be undone",
    confirmVariant: "destructive",
  });
  const onDelete = async () => {
    const ok = await confirm();
    if (ok) {
      mutate({ userId });
    }
  };
  return (
    <>
      <Dialog />
      <LoadingButton
        isLoading={isPending}
        disabled={isPending}
        variant="destructiveOutline"
        size="icon-sm"
        type="button"
        onClick={() => onDelete()}
      >
        <UserX2Icon />
      </LoadingButton>
    </>
  );
};
