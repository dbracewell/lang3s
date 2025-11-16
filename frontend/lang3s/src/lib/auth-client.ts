import { createAuthClient } from "better-auth/react";
import {
  adminClient,
  apiKeyClient,
  inferAdditionalFields,
  usernameClient,
} from "better-auth/client/plugins";
import {
  ac,
  admin,
  analyst,
  dataLoader,
  modeller,
  user,
} from "@/features/auth/permissions";

export const authClient = createAuthClient({
  plugins: [
    inferAdditionalFields(),
    usernameClient(),
    apiKeyClient(),
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
  ],
});

export type Session = typeof authClient.$Infer.Session;

export const { signIn, useSession, changePassword } = createAuthClient();
