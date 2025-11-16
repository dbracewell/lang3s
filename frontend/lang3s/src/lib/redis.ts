import { createClient, RedisClientType } from "redis";
import { env } from "@/env/env";

export const ANNOTATION_QUEUE = "doc_queue";

const globalForRedis = global as unknown as { redis: RedisClientType };

export const getRedisClient = async (): Promise<RedisClientType> => {
  if (globalForRedis.redis) {
    return globalForRedis.redis;
  }
  const client = createClient({
    url: `redis://${env.REDIS_HOST}:${env.REDIS_PORT}/${env.REDIS_DB}`,
  }).on("error", (err) => console.log(err));

  await client.connect();

  if (env.NODE_ENV !== "production")
    globalForRedis.redis = client as RedisClientType;

  return client as RedisClientType;
};

// export async function performRedisCommand(
//   cmd: (client: RedisClientType) => Promise<void>,
// ) {
//   await cmd(client as RedisClientType);
//   client.destroy();
// }
