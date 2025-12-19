import { createClient, RedisClientType } from "redis";
import { env } from "@/lib/env/env";

export const ANNOTATION_QUEUE = "doc_queue";

const globalForRedis = global as unknown as { redis: RedisClientType };

export const createDisconnectedClient = () => {
  return createClient({
    url: `redis://${env.REDIS_HOST}:${env.REDIS_PORT}/${env.REDIS_DB}`,
  }).on("error", (err) => console.log(err));
};

export const createRedisClient = async (): Promise<RedisClientType> => {
  const client = createDisconnectedClient();
  return (await client.connect()) as RedisClientType;
};

export const getGlobalConnection = async (): Promise<RedisClientType> => {
  if (globalForRedis.redis) {
    return globalForRedis.redis;
  }
  const client = await createRedisClient();
  if (env.NODE_ENV !== "production")
    globalForRedis.redis = client as RedisClientType;
  return client as RedisClientType;
};
