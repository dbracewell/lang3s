import { db } from "@/db";
import {
  ac,
  admin,
  analyst,
  dataLoader,
  modeller,
  user,
} from "@/features/auth/permissions";
import { betterAuth } from "better-auth";
import { drizzleAdapter } from "better-auth/adapters/drizzle";
import { admin as adminPlugin, apiKey, username } from "better-auth/plugins";
import { nextCookies } from "better-auth/next-js";

export const auth = betterAuth({
  database: drizzleAdapter(db, {
    provider: "pg",
  }),
  emailAndPassword: {
    enabled: true,
    autoSignIn: true,
    minPasswordLength: 8,
    maxPasswordLength: 16,
  },
  plugins: [
    apiKey({
      disableKeyHashing: true,
    }),
    adminPlugin({
      ac: ac,
      roles: { admin, user, analyst, modeller, dataLoader },
      defaultRole: "user",
      adminRoles: ["admin"],
    }),
    username({
      minUsernameLength: 4,
      maxUsernameLength: 15,
      usernameValidator: (username) => {
        return /^[a-zA-Z0-9_-]+$/.test(username);
      },
    }),
    nextCookies(),
  ],
});
