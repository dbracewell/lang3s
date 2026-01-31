import { drizzle } from "drizzle-orm/node-postgres";
import * as schema from "../../src/lib/db/schema";
import { sql } from "drizzle-orm";
import { t3env } from "@/lib/t3env";

async function reset_db() {
  const db = drizzle(t3env.DATABASE_URL, { schema });
  await db.execute(sql`
  DROP MATERIALIZED VIEW IF EXISTS topic_documents;
  `);
  await db.execute(sql`
  DROP MATERIALIZED VIEW IF EXISTS topic_sentences;
  `);
  await db.execute(sql`
  DROP MATERIALIZED VIEW IF EXISTS annotation_co_occurrence;
  `);
  await db.execute(sql`
  DROP MATERIALIZED VIEW IF EXISTS annotation_counts;
  `);
  await db.execute(sql`DROP TABLE IF EXISTS "drizzle"."__drizzle_migrations";`);
}
reset_db().then((db) => {
  console.log("Reset DB done");
});
