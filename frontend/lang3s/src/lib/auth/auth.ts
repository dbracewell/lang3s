import { db } from "@/lib/db";
import {
  ac,
  admin,
  analyst,
  dataLoader,
  modeller,
  user,
} from "@/lib/auth/permissions";
import { betterAuth } from "better-auth";
import { drizzleAdapter } from "better-auth/adapters/drizzle";
import {
  admin as adminPlugin,
  apiKey,
  jwt,
  username,
} from "better-auth/plugins";
import { nextCookies } from "better-auth/next-js";

export const auth = betterAuth({
  database: drizzleAdapter(db, {
    provider: "sqlite",
  }),
  emailAndPassword: {
    enabled: true,
    autoSignIn: true,
    minPasswordLength: 8,
    maxPasswordLength: 16,
  },
  plugins: [
    jwt({
      jwks: {
        rotationInterval: 60 * 60 * 24 * 30,
        gracePeriod: 60 * 60 * 24 * 2,
        keyPairConfig: {
          alg: "RS256",
        },
      },
    }),
    apiKey({
      enableSessionForAPIKeys: true,
      apiKeyHeaders: ["lang3s-api-key"],
      defaultPrefix: "lang3s-api-key-",
      rateLimit: {
        enabled: false,
        timeWindow: 1000 * 60,
        maxRequests: 100,
      },
    }),
    adminPlugin({
      ac: ac,
      roles: {
        admin: admin,
        user: user,
        analyst: analyst,
        modeller: modeller,
        dataLoader: dataLoader,
      },
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

type Session = typeof auth.$Infer.Session;
