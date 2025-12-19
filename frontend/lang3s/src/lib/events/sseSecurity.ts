import { createRedisClient } from "@/lib/redis";

const redis = await createRedisClient();

const MAX_CONN_PER_USER = 1;
const RATE_LIMIT_WINDOW = 60; // seconds
const RATE_LIMIT_MAX = 100;

export async function enforceLimits(userId: string) {
  const connKey = `sse:user:${userId}:connections`;
  const rateKey = `sse:user:${userId}:rate`;

  const replies = await redis
    .multi()
    .incr(rateKey)
    .expire(rateKey, RATE_LIMIT_WINDOW)
    .incr(connKey)
    .expire(connKey, 3600)
    .exec();

  if (!replies) {
    throw new Error("REDIS_MULTI_FAILED");
  }

  const rate = Number(replies[0]);
  const connections = Number(replies[2]);

  if (Number.isNaN(rate) || Number.isNaN(connections)) {
    throw new Error("REDIS_REPLY_INVALID");
  }

  if (rate > RATE_LIMIT_MAX) {
    await redis.decr(connKey);
    throw new Error("RATE_LIMIT");
  }

  if (connections > MAX_CONN_PER_USER) {
    await redis.decr(connKey);
    throw new Error("MAX_CONNECTIONS");
  }

  return connKey;
}

export async function releaseConnection(connKey: string) {
  await redis.decr(connKey);
}
