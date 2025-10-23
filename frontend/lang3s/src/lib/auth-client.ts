import { createAuthClient } from "better-auth/react";
import { usernameClient, adminClient } from "better-auth/client/plugins";
import {
  ac,
  admin,
  analyst,
  dataLoader,
  modeller,
  user,
} from "@/lib/permissions";

export const authClient = createAuthClient({
  plugins: [
    adminClient({
      ac,
      roles: {
        admin,
        user,
        dataLoader,
        analyst,
        modeller,
      },
      defaultRole: "user",
    }),
    usernameClient(),
  ],
});

export const { signIn, useSession, changePassword } = createAuthClient();
