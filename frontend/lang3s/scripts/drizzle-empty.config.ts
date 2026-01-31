import { defineConfig } from "drizzle-kit";
import { t3env } from "@/lib/t3env";

export default defineConfig({
  dialect: "postgresql",
  schema: "./src/lib/db/schemas/auth.ts",
  dbCredentials: {
    url: t3env.DATABASE_URL,
  },
});
