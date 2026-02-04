import { seed_ontology } from "./seed_ontology";
import { getGlobalConnection } from "@/lib/redis";

async function initDb() {
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
