"use client";
import { CardContent, CardFooter } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { LoadingButton } from "@/components/ui/loading-button";
import { authClient } from "@/lib/auth/auth-client";
import { AuthPageCard } from "@/features/auth/ui/components/AuthPageCard";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";
import { CHAT_HISTORY_STORAGE_KEY } from "@/features/chat/constants";

export const SignInPageView = ({ redirect }: { redirect?: string }) => {
  const [isPending, setIsPending] = useState(false);
  const router = useRouter();
  const queryClient = useQueryClient();

  const onSubmit = async (formData: FormData) => {
    const username = formData.get("username") as string;
    const password = formData.get("password") as string;
    const { error } = await authClient.signIn.username({
      username,
      password,
      fetchOptions: {
        onRequest: () => setIsPending(true),
        onResponse: () => setIsPending(false),
        onSuccess: async () => {
          localStorage.removeItem(CHAT_HISTORY_STORAGE_KEY);
          await queryClient.invalidateQueries({});
          router.push(redirect ?? "/");
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
            <label htmlFor="username" className="text-sm dark:text-slate-200">
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
            <label htmlFor="password" className="text-sm dark:text-slate-200">
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
