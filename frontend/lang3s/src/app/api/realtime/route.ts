import { NextRequest, NextResponse } from "next/server";
import { getUser } from "@/features/auth/server/actions";
import { enforceLimits, releaseConnection } from "@/lib/events/sseSecurity";
import { redisFanout } from "@/lib/events/redisFanout";
import { EventMessageSchema } from "@/lib/events/events";

/**
 * IMPORTANT:
 * - SSE requires Node.js runtime (not Edge)
 * - Disable body parsing & caching implicitly by streaming
 */
export const runtime = "nodejs";

export async function GET(req: NextRequest) {
  const user = await getUser();
  if (user == null) {
    return new NextResponse("Unauthorized", { status: 401 });
  }

  await redisFanout.ensureReady();

  let connKey: string;
  try {
    connKey = await enforceLimits(user.id);
  } catch (err) {
    return new Response(
      (err as Error).message === "RATE_LIMIT"
        ? "Too many attempts"
        : "Too many connections",
      { status: 429 },
    );
  }

  const stream = new ReadableStream({
    start(controller) {
      const encoder = new TextEncoder();
      let closed = false;

      const send = (data: string) => controller.enqueue(encoder.encode(data));

      // Initial comment
      send(": connected\n\n");

      // Heartbeat
      const heartbeat = setInterval(() => {
        send(": keep-alive\n\n");
      }, 15_000);

      // Redis listener
      const listener = (message: string) => {
        try {
          const data = JSON.parse(message);
          const event = EventMessageSchema.parse(data);
          if (
            (user.role === "admin" && event.type.startsWith("job")) ||
            event.userid === user.id
          ) {
            send(`event: message\n`);
            send(`data: ${message}\n\n`);
            console.log("Sending >", message);
          }
        } catch (e) {
          console.error(e);
        }
      };

      redisFanout.add(listener);

      const cleanup = async () => {
        if (closed) return;
        closed = true;
        clearInterval(heartbeat);
        redisFanout.remove(listener);
        try {
          await releaseConnection(connKey);
        } catch {
          /* ignore */
        }

        try {
          controller.close(); // safe now
        } catch {
          /* ignore */
        }
      };

      req.signal.addEventListener("abort", cleanup);
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
