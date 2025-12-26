"use client";
import { InputFormField } from "@/components/form-controls/input-form-field";
import { CardContent, CardFooter } from "@/components/ui/card";
import { Form } from "@/components/ui/form";
import { LoadingButton } from "@/components/ui/loading-button";
import { createAdminAccount } from "@/features/auth/server/actions";
import { AuthPageCard } from "@/features/auth/ui/components/AuthPageCard";
import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import {
  AdminAccountSchema,
  AdminAccountSchemaType,
} from "@/features/auth/schemas";

export const InstallPageView = () => {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const form = useForm<AdminAccountSchemaType>({
    resolver: zodResolver(AdminAccountSchema),
  });

  const onSubmit = (values: AdminAccountSchemaType) => {
    startTransition(async () => {
      const response = await createAdminAccount(values);
      if (response == null) {
        toast.error("Internal server error, please try again.");
      } else {
        switch (response.status) {
          case 401:
            toast.error("Invalid administrator passphrase");
            break;
          case 400:
            toast.error("Invalid data");
            break;
          case 200:
            router.push("/");
            break;
          default:
            toast.error("Internal server error, please try again.");
            break;
        }
      }
    });
  };

  return (
    <AuthPageCard
      title="Create your administrator account"
      description="Enter your information below to create your account"
    >
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)}>
          <CardContent className="cols mb-5 gap-6">
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
            <InputFormField
              reactHookForm={form}
              label="Admin Passphrase"
              name="passphrase"
              disabled={isPending}
            />
          </CardContent>
          <CardFooter>
            <LoadingButton
              isLoading={isPending}
              className="w-full"
              disabled={isPending}
            >
              Create
            </LoadingButton>
          </CardFooter>
        </form>
      </Form>
    </AuthPageCard>
  );
};
