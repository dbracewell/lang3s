import {
  ac,
  admin,
  analyst,
  dataLoader,
  modeller,
  user as userPermissions,
  user,
} from "@/lib/auth/permissions";
import { betterAuth } from "better-auth";
import { admin as adminPlugin, jwt, username } from "better-auth/plugins";
import { apiKey } from "@better-auth/api-key";
import { nextCookies } from "better-auth/next-js";
import { t3env } from "@/lib/t3env";
import Database from "better-sqlite3";

export const getPermissionsForRole = (
  userRole: string | null | undefined,
): Record<string, readonly string[]> => {
  const role = userRole ?? "user";
  if (role === "admin") {
    return admin.statements;
  } else if (role === "modeller") {
    return modeller.statements;
  } else if (role === "analyst") {
    return analyst.statements;
  } else if (role === "dataLoader") {
    return dataLoader.statements;
  }
  return userPermissions.statements;
};

export const auth = betterAuth({
  database: new Database(t3env.DATABASE_URL),
  user: {
    additionalFields: {
      role: {
        type: "string",
        input: false,
        required: false,
        defaultValue: "user",
      },
    },
  },
  emailAndPassword: {
    enabled: true,
    autoSignIn: true,
    minPasswordLength: 8,
    maxPasswordLength: 16,
  },
  plugins: [
    jwt({
      jwt: {
        definePayload: ({ user }) => {
          return {
            id: user.id,
            role: user.role,
            permissions: getPermissionsForRole(user.role),
          };
        },
      },
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
  databaseHooks: {
    user: {
      create: {
        before: async (user, ctx) => {
          let role = "user";
          const adminKey = ctx!.query?.adminKey;
          if (adminKey === t3env.ADMIN_PASSPHRASE) {
            role = "admin";
          }

          return {
            data: {
              ...user,
              role,
            },
          };
        },
      },
    },
  },
});
