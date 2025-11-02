"use client";
import { CopyButton } from "@/components/CopyButton";
import { DeleteButton } from "@/components/DeleteButton";
import { Button } from "@/components/ui/button";
import { roleHasPermissions } from "@/modules/auth/permissions";
import { FullUserInfo } from "@/modules/common/types";
import { useTRPCMutation } from "@/trpc/use-mutation";
import { KeyIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

export const UserApiKeys = ({ user }: { user: FullUserInfo }) => {
  if (!roleHasPermissions(user.role, ["data:load", "model:create"])) {
    return null;
  }
  const [apiKeyDeleting, setApiKeyDeleting] = useState("");
  const router = useRouter();
  const deleteApiKey = useTRPCMutation((trpc) => ({
    mutation: trpc.auth.deleteApiKey.mutationOptions({
      onMutate: (v) => setApiKeyDeleting(v.id),
      onSuccess: () => {
        router.replace("/account");
        setApiKeyDeleting("");
      },
    }),
    successToast: "Successfully deleted api key",
    errorToast: "Failed to delete api key",
  }));
  const generateApiKey = useTRPCMutation((trpc) => ({
    mutation: trpc.auth.createApiKey.mutationOptions({
      onSuccess: () => router.replace("/account"),
    }),
    successToast: "Successfully created an api key",
    errorToast: "Failed to create an api key",
  }));

  return (
    <>
      <div className="bg-border my-2 flex h-[1px] flex-col" />
      <div className="mb-4 flex items-center justify-between gap-2">
        <h1 className="flex items-center gap-2">
          <KeyIcon /> Api Keys
        </h1>
        <Button
          onClick={() => generateApiKey.mutate()}
          disabled={generateApiKey.isPending}
        >
          Generate API Key
        </Button>
      </div>
      <div className="flex flex-col gap-3">
        {user.keys?.map((k, i) => (
          <div
            className="flex flex-col gap-1 rounded-lg border bg-slate-100 p-2"
            key={k.name ?? i}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium">{k.name ?? "ApiKey"}</span>
              <div className="flex items-center gap-2">
                <DeleteButton
                  className="border-0 bg-transparent"
                  isDeleting={apiKeyDeleting === k.id}
                  onDelete={() => deleteApiKey.mutate({ id: k.id })}
                />
                <CopyButton text={k.key} />
              </div>
            </div>
            <div
              className="truncate blur-[3px]"
              style={{
                userSelect: "none",
                WebkitUserSelect: "none",
                msUserSelect: "none",
              }}
            >
              {k.key}
            </div>
          </div>
        ))}
      </div>
    </>
  );
};
