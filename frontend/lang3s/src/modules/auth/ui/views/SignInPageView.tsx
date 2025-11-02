"use client";
import { CardContent, CardFooter } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { LoadingButton } from "@/components/ui/loading-button";
import { authClient } from "@/lib/auth-client";
import { AuthPageCard } from "@/modules/auth/ui/components/AuthPageCard";
import { useTRPC } from "@/trpc/client";
import { useQueryClient } from "@tanstack/react-query";
import { redirect, useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

export const SignInPageView = () => {
  const [isPending, setIsPending] = useState(false);
  const queryClient = useQueryClient();
  const trpc = useTRPC();
  const router = useRouter();

  const onSubmit = async (formData: FormData) => {
    const username = formData.get("username") as string;
    const password = formData.get("password") as string;
    queryClient.invalidateQueries(trpc.auth.getCurrentUser.queryOptions());
    const { error } = await authClient.signIn.username({
      username,
      password,
      callbackURL: "/",
      fetchOptions: {
        onRequest: () => setIsPending(true),
        onResponse: () => setIsPending(false),
        onSuccess: async () => {
          router.push("/");
        },
      },
    });
    if (error) {
      toast.error(error.message);
    }
  };

  return (
    <AuthPageCard
      title="Login to your account"
      description="Enter your username below to login to your account"
    >
      <form action={onSubmit}>
        <CardContent className="cols mb-5 gap-6">
          <div className="cols gap-1">
            <label htmlFor="username" className="text-primary text-sm">
              Username
            </label>
            <Input
              id="username"
              name="username"
              required
              disabled={isPending}
            />
          </div>
          <div className="cols gap-1">
            <label htmlFor="password" className="text-primary text-sm">
              Password
            </label>
            <Input
              id="password"
              name="password"
              type="password"
              required
              disabled={isPending}
            />
          </div>
        </CardContent>
        <CardFooter>
          <LoadingButton
            isLoading={isPending}
            className="w-full"
            disabled={isPending}
          >
            Sign in
          </LoadingButton>
        </CardFooter>
      </form>
    </AuthPageCard>
  );
};
