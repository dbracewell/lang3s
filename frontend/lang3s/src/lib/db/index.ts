import { drizzle } from "drizzle-orm/libsql";
import * as schema from "./schema";
import { t3env } from "@/lib/t3env";

export const db = drizzle(t3env.DATABASE_URL, { schema });
