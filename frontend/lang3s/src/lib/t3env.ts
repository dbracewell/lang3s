import { createEnv } from "@t3-oss/env-nextjs";
import { z } from "zod";

export const t3env = createEnv({
  server: {
    EMBEDDING_SERVER: z.url(),
    REDIS_HOST: z.hostname(),
    REDIS_PORT: z.coerce.number().int(),
    REDIS_DB: z.coerce.number().int(),
    ADMIN_PASSPHRASE: z.string(),
    SYSTEM_KEY: z.string(),
    DATABASE_URL: z.url(),
    BETTER_AUTH_SECRET: z.string(),
    BETTER_AUTH_URL: z.url(),
    NODE_ENV: z.string().optional(),
    DOCUMENTS_DIR: z.string(),
    FILESTORE_ROOT: z.string(),
    PYTHON_SERVER: z.string(),
  },
  client: {
    NEXT_PUBLIC_APP_URL: z.url(),
  },
  emptyStringAsUndefined: true,
  experimental__runtimeEnv: {
    NEXT_PUBLIC_APP_URL: process.env.NEXT_PUBLIC_APP_URL,
  },
});
