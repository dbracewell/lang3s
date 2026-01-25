import { createClient, RedisClientType } from "redis";
import { t3env } from "@/lib/t3env";

export const ANNOTATION_QUEUE = "annotation_queue";

const globalForRedis = global as unknown as { redis: RedisClientType };

export const createDisconnectedClient = () => {
  return createClient({
    url: `redis://${t3env.REDIS_HOST}:${t3env.REDIS_PORT}/${t3env.REDIS_DB}`,
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
  if (t3env.NODE_ENV !== "production")
    globalForRedis.redis = client as RedisClientType;
  return client as RedisClientType;
};
