import { initSharedWorker } from "@/lib/events/sharedWorkerClient";
import { initEventManager } from "@/lib/events/eventManager";

export function initRealtime() {
  if (typeof window === "undefined") return;

  if ("SharedWorker" in window) {
    initSharedWorker();
  } else {
    initEventManager();
  }
}
