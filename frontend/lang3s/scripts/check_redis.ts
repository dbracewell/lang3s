import { ANNOTATION_QUEUE, getGlobalConnection } from "@/lib/redis";

const main = async () => {
  const client = await getGlobalConnection();

  try {
    const size = await client.lLen(ANNOTATION_QUEUE);
    console.log("SIZE:", size);
  } finally {
    await client.quit();
    console.log("Redis client disconnected");
  }
};

main();
