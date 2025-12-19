import { getGlobalConnection } from "@/lib/redis";

const main = async () => {
  const client = await getGlobalConnection();

  try {
    const size = await client.flushAll();
  } finally {
    await client.quit();
    console.log("Redis client disconnected");
  }
};

main();
