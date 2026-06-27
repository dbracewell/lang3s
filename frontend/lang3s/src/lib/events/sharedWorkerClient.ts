"use client";

import { eventBus } from "@/lib/events/eventBus";
import { parseEventMessage } from "@/lib/events/events";

declare global {
  var __sharedEventWorker: SharedWorker | undefined;

  var _sharedEventPortStarted: boolean | undefined;
}

export function initSharedWorker() {
  if (typeof window === "undefined") return;

  if (!globalThis.__sharedEventWorker) {
    globalThis.__sharedEventWorker = new SharedWorker("/sse.worker.js");
  }
  const worker = globalThis.__sharedEventWorker;

  if (!globalThis._sharedEventPortStarted) {
    globalThis._sharedEventPortStarted = true;

    worker.port.start();

    worker.port.onmessage = (evt) => {
      const msg = evt.data;
      if (msg?.kind === "status") {
        return;
      }

      if (msg?.kind === "sse") {
        const parsed = parseEventMessage(msg.data);
        if (parsed) {
          eventBus.emit(parsed.type, parsed.data);
        }
      }
    };
  }

  worker.port.postMessage({ kind: "start", url: "/api/realtime" });
}
