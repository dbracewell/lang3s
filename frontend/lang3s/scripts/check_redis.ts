import { ANNOTATION_QUEUE, getRedisClient } from "@/lib/redis";

const main = async () => {
  const client = await getRedisClient();

  try {
    const size = await client.lLen(ANNOTATION_QUEUE);
    console.log("SIZE:", size);
  } finally {
    await client.quit();
    console.log("Redis client disconnected");
  }
};

main();
