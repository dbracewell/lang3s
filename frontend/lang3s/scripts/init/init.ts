import { seed_ontology } from "./seed_ontology";
import { getGlobalConnection } from "@/lib/redis";
import { db } from "@/lib/db";
import { ConfigTable } from "@/lib/db/schemas/config";
import default_config from "./settings.json";

async function initDb() {
  await seed_ontology();

  const config_values = Object.entries(default_config).map(([k, v]) => ({
    name: k,
    value: v,
  }));
  await db.insert(ConfigTable).values(config_values);

  const client = await getGlobalConnection();

  try {
    await client.flushAll();
  } finally {
    await client.quit();
    console.log("Redis client disconnected");
  }
}

initDb();
