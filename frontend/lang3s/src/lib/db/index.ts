import { drizzle } from "drizzle-orm/node-postgres";
import * as schema from "./schema";
import { env } from "@/lib/env/env";

export const db = drizzle(env.DATABASE_URL, { schema });
