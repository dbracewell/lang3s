"use client";
import { InputFormField } from "@/components/form-controls/input-form-field";
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
import { UserRoleDescriptions, UserRoles } from "@/features/auth/permissions";
import { useTRPCMutation } from "@/lib/trpc/use-mutation";
import { zodResolver } from "@hookform/resolvers/zod";
import { UserRoundPlusIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import {
  UserAccountSchema,
  UserAccountSchemaType,
} from "@/features/auth/schemas";

export const AddUserDialog = () => {
  const router = useRouter();

  const { isPending, mutate } = useTRPCMutation((trpc) => ({
    mutation: trpc.auth.createUser.mutationOptions({
      onError: () => toast.error("Something went wrong"),
      onSuccess: (data) => {
        if (data.code === 200) {
          toast.success("Successfully created user");
          router.replace("/admin/users");
          onClose();
          return;
        } else {
          if (data.path) {
            form.setError(data.path as "username" | "email", {
              type: "server",
              message: data.message,
            });
            return;
          }
          toast.error(data.message ?? "Something went wrong");
        }
      },
    }),
  }));

  const form = useForm<UserAccountSchemaType>({
    resolver: zodResolver(UserAccountSchema),
    defaultValues: {
      email: "",
      name: "",
      username: "",
      password: "",
      role: "user",
    },
  });
  const [open, setOpen] = useState(false);

  const onClose = (force: boolean = false) => {
    if (isPending && force) {
      return;
    }
    if (open) {
      form.reset();
    }
    setOpen((prev) => {
      return !prev;
    });
  };

  const handleSubmit = (values: UserAccountSchemaType) => {
    mutate({
      ...values,
    });
  };

  const role = form.watch("role");

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogTrigger asChild>
        <Button variant="listButton" size="sm">
          <UserRoundPlusIcon /> Add User
        </Button>
      </DialogTrigger>
      <Form {...form}>
        <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-6">
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add User</DialogTitle>
              <DialogDescription>
                Add a new user to the system
              </DialogDescription>
            </DialogHeader>
            <InputFormField
              reactHookForm={form}
              label="Name"
              name="name"
              disabled={isPending}
            />
            <InputFormField
              reactHookForm={form}
              label="Email"
              name="email"
              placeholder="user@example.com"
              disabled={isPending}
            />
            <InputFormField
              reactHookForm={form}
              label="Username"
              name="username"
              disabled={isPending}
            />
            <InputFormField
              reactHookForm={form}
              label="Password"
              name="password"
              type="password"
              disabled={isPending}
            />
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
            <DialogFooter>
              <DialogClose asChild>
                <Button type="button" variant="outline" disabled={isPending}>
                  Cancel
                </Button>
              </DialogClose>
              <LoadingButton
                isLoading={isPending}
                onClick={form.handleSubmit(handleSubmit)}
              >
                Create User
              </LoadingButton>
            </DialogFooter>
          </DialogContent>
        </form>
      </Form>
    </Dialog>
  );
};
