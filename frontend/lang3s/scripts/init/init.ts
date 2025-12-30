import { db } from "@/lib/db";
import { MetadataTable } from "@/lib/db/schemas/metadata";
import { seed_ontology } from "./seed_ontology";
import { getGlobalConnection } from "@/lib/redis";

async function initDb() {
  await db
    .insert(MetadataTable)
    .values([
      {
        source: "document",
        name: "language",
        dataType: "string",
      },
      {
        source: "document",
        name: "mime-type",
        dataType: "string",
      },
    ])
    .execute();

  await seed_ontology();

  const client = await getGlobalConnection();

  try {
    const size = await client.flushAll();
  } finally {
    await client.quit();
    console.log("Redis client disconnected");
  }
}

initDb();
