import { NextRequest } from "next/server";
import { getCurrentUser } from "@/features/auth/server/actions";
import { createRedisClient } from "@/lib/redis";
import { EventType } from "@/lib/events/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const adminCanSee: EventType[] = ["job:update"];

export async function GET(req: NextRequest) {
  const user = await getCurrentUser();
  const subscriber = await createRedisClient();

  const stream = new ReadableStream({
    async start(controller) {
      await subscriber.subscribe("lang3s-events", (message) => {
        try {
          const data = JSON.parse(message);
          const { type, userId } = data;
          if (
            userId === user.id ||
            (user.role === "admin" && adminCanSee.includes(type))
          ) {
            const sseMessage = `data: ${message}\n\n`;
            controller.enqueue(new TextEncoder().encode(sseMessage));
          }
        } catch (err) {
          console.error(err);
        }
      });
      controller.enqueue(
        new TextEncoder().encode("event: connected\ndata: true\n\n"),
      );
    },
    async cancel() {
      await subscriber.unsubscribe("lang3s-events");
      await subscriber.quit();
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
