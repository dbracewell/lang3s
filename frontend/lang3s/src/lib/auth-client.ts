import { createAuthClient } from "better-auth/react";
import {
  usernameClient,
  adminClient,
  inferAdditionalFields,
  apiKeyClient,
} from "better-auth/client/plugins";
import {
  ac,
  admin,
  analyst,
  dataLoader,
  modeller,
  user,
} from "@/modules/auth/permissions";

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
