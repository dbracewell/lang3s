import { authClient } from "@/lib/auth/auth-client";
import { toast } from "sonner";
import { CHAT_HISTORY_STORAGE_KEY } from "@/features/chat/constants";

export const logout = (onSuccess: () => void) => {
  authClient.signOut({
    fetchOptions: {
      onSuccess() {
        localStorage.removeItem(CHAT_HISTORY_STORAGE_KEY);
        onSuccess();
      },
      onError({ error }) {
        toast.error(error.message);
      },
    },
  });
};
