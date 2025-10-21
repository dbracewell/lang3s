import { createAuthClient } from "better-auth/react";
import { usernameClient, adminClient } from "better-auth/client/plugins";

export const authClient = createAuthClient({
   plugins: [adminClient(), usernameClient()],
});

export const { signIn, useSession, changePassword } = createAuthClient();
