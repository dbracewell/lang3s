import "server-only";
import { createRedisClient } from "@/lib/redis";
import { EventPayloadMap } from "@/lib/events/schemas";
import { EventType } from "@/lib/events/types";

export async function publishMessage<K extends EventType>({
  messageType,
  payload,
  userId,
}: {
  messageType: K;
  payload: EventPayloadMap[K];
  userId: string;
}) {
  const client = await createRedisClient();
  try {
    await client.publish(
      "events",
      JSON.stringify({
        type: messageType,
        userid: userId,
        payload,
      }),
    );
  } catch (e) {
    console.error(e);
  } finally {
    await client.close();
  }
}
