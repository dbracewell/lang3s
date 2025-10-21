import { betterAuth } from "better-auth";
import { drizzleAdapter } from "better-auth/adapters/drizzle";
import { admin as adminPlugin, username } from "better-auth/plugins";
import {
   ac,
   admin,
   analyst,
   dataLoader,
   modeller,
   user,
} from "@/lib/permissions";
import { db } from "@/db";

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
      adminPlugin({
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
      username(),
   ],
});
