"use client";
import { CheckboxFormField } from "@/components/form-controls/checkbox-form-field";
import { SelectFormField } from "@/components/form-controls/select-form-field";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Form } from "@/components/ui/form";
import { LoadingButton } from "@/components/ui/loading-button";
import { UserType } from "@/features/auth/ui/components/UserListColumns";
import { UserRoleDescriptions, UserRoles } from "@/features/auth/permissions";
import { useTRPCMutation } from "@/lib/trpc/use-mutation";
import { zodResolver } from "@hookform/resolvers/zod";
import { PencilIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import z from "zod";

export const UserRoleSchema = z.object({
  role: z.enum(UserRoles),
  isActive: z.boolean(),
});
type UserRoleSchemaType = z.infer<typeof UserRoleSchema>;

export const EditUserDialog = ({ row }: { row: UserType }) => {
  const [open, setOpen] = useState(false);
  const router = useRouter();

  const { isPending, mutate } = useTRPCMutation((trpc) => ({
    mutation: trpc.auth.updateUser.mutationOptions({
      onSuccess: () => {
        router.replace("/admin/users");
        onClose();
      },
    }),
    successToast: "Successfully updated user",
    errorToast: "Failed to update user",
  }));

  const form = useForm<UserRoleSchemaType>({
    resolver: zodResolver(UserRoleSchema),
    defaultValues: {
      role: row.role,
      isActive: !row.banned,
    },
  });

  const onClose = () => {
    if (isPending) {
      return;
    }
    if (open === true) {
      form.reset();
    }
    setOpen((prev) => {
      if (prev === false) {
        return true;
      }
      return false;
    });
  };

  const handleSubmit = (values: UserRoleSchemaType) => {
    mutate({
      userId: row.id,
      ...values,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogTrigger asChild>
        <Button variant="outline" size="icon-sm" type="button">
          <PencilIcon className="size-4" />
        </Button>
      </DialogTrigger>
      <Form {...form}>
        <form onSubmit={form.handleSubmit(handleSubmit)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Edit User</DialogTitle>
              <DialogDescription>
                Change a user's role or mark their account as inactive
              </DialogDescription>
            </DialogHeader>
            <SelectFormField
              reactHookForm={form}
              label="Role"
              name="role"
              disabled={isPending}
              defaultValue="user"
              selectTriggerClassName="group is-inactive"
              options={UserRoles.map((role) => ({
                type: "item",
                value: role,
                label: role.toUpperCase(),
                node: (
                  <div className="flex flex-col items-start gap-0.5 text-sm">
                    <span>{role.toUpperCase()}</span>
                    <span className="group-[.is-inactive]:hidden">
                      {UserRoleDescriptions[role]}
                    </span>
                  </div>
                ),
              }))}
            />
            <CheckboxFormField
              reactHookForm={form}
              name="isActive"
              label="Active Account"
            />
            <DialogFooter>
              <DialogClose asChild>
                <Button type="button" variant="outline" disabled={isPending}>
                  Cancel
                </Button>
              </DialogClose>
              <LoadingButton
                isLoading={isPending}
                disabled={isPending}
                type="submit"
                onClick={form.handleSubmit(handleSubmit)}
              >
                Update Role
              </LoadingButton>
            </DialogFooter>
          </DialogContent>
        </form>
      </Form>
    </Dialog>
  );
};
