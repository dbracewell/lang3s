import "server-only";
import { createClient, RedisClientType } from "redis";

export const ANNOTATION_QUEUE = "doc_queue";

export async function performRedisCommand(
  cmd: (client: RedisClientType) => Promise<void>,
) {
  const client = createClient({
    url: "redis://localhost:6379/0",
  })
    .on("connect", () => console.log("Redis client connected"))
    .on("error", (err) => console.log(err));
  await client.connect();
  await cmd(client as RedisClientType);
  client.destroy();
}
