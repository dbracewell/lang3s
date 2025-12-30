import { drizzle } from "drizzle-orm/node-postgres";
import * as schema from "../../src/lib/db/schema";
import { sql } from "drizzle-orm";

async function reset_db() {
  const db = drizzle(process.env.DATABASE_URL!, { schema });
  await db.execute(sql`
  DROP MATERIALIZED VIEW IF EXISTS topic_documents;
  `);
  await db.execute(sql`
  DROP MATERIALIZED VIEW IF EXISTS topic_sentences;
  `);
  await db.execute(sql`DROP TABLE IF EXISTS "drizzle"."__drizzle_migrations";`);
}
reset_db().then((db) => {
  console.log("Reset DB done");
});
