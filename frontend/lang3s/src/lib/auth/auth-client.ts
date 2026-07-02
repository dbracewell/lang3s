import { createAuthClient } from "better-auth/react";
import {
  adminClient,
  apiKeyClient,
  inferAdditionalFields,
  jwtClient,
  usernameClient,
} from "better-auth/client/plugins";
import {
  ac,
  admin,
  analyst,
  dataLoader,
  modeller,
  user,
} from "@/lib/auth/permissions";
import { nextCookies } from "better-auth/next-js";

export const authClient = createAuthClient({
  plugins: [
    inferAdditionalFields(),
    jwtClient(),
    usernameClient(),
    apiKeyClient(),
    adminClient({
      ac: ac,
      roles: {
        admin: admin,
        user: user,
        analyst: analyst,
        modeller: modeller,
        dataLoader: dataLoader,
      },
    }),
    nextCookies(),
  ],
});

export type Session = typeof authClient.$Infer.Session;
