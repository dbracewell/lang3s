"use client";
import { useConfirmationDialog } from "@/components/dialogs/ConfirmationDialog";
import { LoadingButton } from "@/components/ui/loading-button";
import { UserX2Icon } from "lucide-react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { removeUser } from "@/features/auth/server/actions";
import { useMutation } from "@tanstack/react-query";

export const DeleteUser = ({ userId }: { userId: string }) => {
  const router = useRouter();
  const { isPending, mutate } = useMutation({
    mutationFn: removeUser,
    onSuccess: (data) => {
      if (data) {
        toast.success("Successfully removed user");
        router.replace("/admin/users");
        return;
      } else {
        toast.error("Failed to delete user");
      }
    },
  });
  const { confirm, Dialog } = useConfirmationDialog({
    title: "Delete user",
    description: "This action cannot be undone",
    confirmVariant: "destructive",
  });
  const onDelete = async () => {
    const ok = await confirm();
    if (ok) {
      mutate(userId);
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
