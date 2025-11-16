import { getRedisClient } from "@/lib/redis";

const main = async () => {
  const client = await getRedisClient();

  try {
    const size = await client.flushAll();
  } finally {
    await client.quit();
    console.log("Redis client disconnected");
  }
};

main();
