import { createEnv } from "@t3-oss/env-nextjs";
import { z } from "zod";

export const t3env = createEnv({
  server: {
    INNGEST_URL: z.string(),
    INNGEST_SIGNING_KEY: z.string(),
    // Docker service/container names may include underscores (e.g. lang3s_redis),
    // which are not valid RFC hostnames but do resolve on Docker networks.
    REDIS_HOST: z.string().min(1),
    REDIS_PORT: z.coerce.number().int(),
    REDIS_DB: z.coerce.number().int(),
    ADMIN_PASSPHRASE: z.string(),
    SYSTEM_KEY: z.string(),
    DATABASE_URL: z.string().default("users.db"),
    BETTER_AUTH_SECRET: z.string(),
    BETTER_AUTH_URL: z.url(),
    NODE_ENV: z.string().optional(),
    FILESTORE_ROOT: z.string(),
  },
  client: {
    NEXT_PUBLIC_APP_URL: z.url(),
    NEXT_PUBLIC_BACKEND_URL: z.url(),
  },
  emptyStringAsUndefined: true,
  experimental__runtimeEnv: {
    NEXT_PUBLIC_APP_URL: process.env.NEXT_PUBLIC_APP_URL,
    NEXT_PUBLIC_BACKEND_URL: process.env.NEXT_PUBLIC_BACKEND_URL,
  },
});
