"use client";
import { DeleteButton } from "@/components/buttons/DeleteButton";
import { Button } from "@/components/ui/button";
import { FullUserInfo } from "@/lib/types";
import { KeyIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { authClient } from "@/lib/auth/auth-client";
import { toast } from "sonner";
import { randomAlphaUnderscore } from "@/lib/utils/random";
import { useUser } from "@/features/auth/contexts/UserContext";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { CopyButton } from "@/components/buttons/CopyButton";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils/cn";

export const UserApiKeys = ({ user }: { user: FullUserInfo }) => {
  const [apiKeyDeleting, setApiKeyDeleting] = useState("");
  const router = useRouter();
  const queryClient = useQueryClient();
  const deleteApiKey = useMutation({
    mutationFn: async (id: string) => {
      return await authClient.apiKey.delete({
        keyId: id,
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["apiKeys", user.id],
      });
      router.refresh();
      setApiKeyDeleting("");
      toast.success("Successfully deleted the api key");
    },
    onError: async () => {
      toast.error("Error while deleting the api key");
    },
  });

  return (
    <div className="flex flex-col">
      <div className="bg-heading flex items-center justify-between gap-2 rounded-t-lg border border-b-0 p-2 text-white">
        <h2 className="flex items-center gap-2 text-2xl font-semibold">
          <KeyIcon /> Api Keys
        </h2>
        <NewAPIKeyDialog setApiKeyDeleting={setApiKeyDeleting} />
      </div>
      <div className="flex flex-1 flex-col gap-3">
        {user.keys?.map((k, i) => (
          <div
            className="flex flex-col gap-1 border border-b-0 bg-slate-100 p-2 last:rounded-b-lg last:border-b dark:bg-slate-900"
            key={k.name ?? i}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium">{k.name ?? "ApiKey"}</span>
              <div className="flex items-center gap-2">
                <DeleteButton
                  className="border-0 bg-transparent"
                  isDeleting={apiKeyDeleting === k.id}
                  onDelete={() => deleteApiKey.mutate(k.id)}
                />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const NewAPIKeyDialog = ({
  setApiKeyDeleting,
}: {
  setApiKeyDeleting: (v: string) => void;
}) => {
  const queryClient = useQueryClient();
  const user = useUser();
  const router = useRouter();
  const [showModal, setShowModal] = useState(false);
  const [keyName, setKeyName] = useState(`Key-${randomAlphaUnderscore(5)}`);
  const [apiKey, setApiKey] = useState("");
  const generateApiKey = useMutation({
    mutationFn: async () => {
      return await authClient.apiKey.create({
        name: keyName.trim(),
      });
    },
    onSuccess: async (data) => {
      if (data.error) {
        toast.error("Error while creating an api key");
        return;
      }
      await queryClient.invalidateQueries({
        queryKey: ["apiKeys", user.id],
      });
      router.refresh();
      setApiKeyDeleting("");
      setApiKey(data.data.key);
    },
    onError: async () => {
      toast.error("Error while creating an api key");
    },
  });

  const onOpenChange = (value: boolean) => {
    if (generateApiKey.isPending) {
      return;
    }
    setApiKeyDeleting("");
    setApiKey("");
    setKeyName(`Key-${randomAlphaUnderscore(5)}`);
    setShowModal(value);
  };

  return (
    <Dialog open={showModal} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <Button variant="outline">Generate API Key</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Generate API Key</DialogTitle>
          <DialogDescription className="sr-only">
            Generate a new API Key
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-2">
          <Label>Key Name</Label>
          <Input
            value={keyName}
            disabled={generateApiKey.isPending || !!apiKey}
            placeholder="Key Name..."
            onChange={(e) => setKeyName(e.target.value)}
          />
          <Label>API Key</Label>
          <div
            className={cn(
              "flex items-center p-1",
              !!apiKey && "border-dodger-blue-500 rounded-md border",
            )}
          >
            <Input
              disabled
              value={apiKey}
              className="disabled:text-muted-foreground! truncate border-0! bg-transparent! disabled:opacity-100!"
            />
            <CopyButton disabled={!apiKey} text={apiKey} />
          </div>
        </div>
        <DialogFooter>
          {!apiKey ? (
            <>
              <Button
                variant="outline"
                disabled={generateApiKey.isPending}
                onClick={() => onOpenChange(false)}
              >
                Cancel
              </Button>
              <Button
                autoFocus
                disabled={
                  generateApiKey.isPending || !!apiKey || !keyName.trim()
                }
                onClick={() => generateApiKey.mutate()}
              >
                Create
              </Button>
            </>
          ) : (
            <div className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">
                API Key successfully generated.
              </span>
              <Button onClick={() => onOpenChange(false)}>Close</Button>
            </div>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
