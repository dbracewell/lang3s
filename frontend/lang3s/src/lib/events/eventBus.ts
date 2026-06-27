import type { SSEEventMap } from "./events";
import { EventType } from "@/lib/events/eventSchemas";

type AnyHandler = (payload: unknown) => void;

export class EventBus {
  private handlers: Partial<Record<EventType, Set<AnyHandler>>> = {};

  on<K extends EventType>(
    type: K,
    handler: (payload: SSEEventMap[K]) => void,
  ): () => void {
    const set = (this.handlers[type] ??= new Set<AnyHandler>());

    const wrapped: AnyHandler = (payload) => {
      handler(payload as SSEEventMap[K]);
    };

    set.add(wrapped);

    return () => {
      set.delete(wrapped);
      if (set.size === 0) delete this.handlers[type];
    };
  }

  emit<K extends EventType>(type: K, payload: SSEEventMap[K]) {
    console.log("EVENT BUS", type);
    console.log("EVENT BUS", payload);
    const set = this.handlers[type];
    console.log("EVENT BUS", set);
    if (!set) return;
    for (const h of set) h(payload);
  }

  clear(type?: EventType) {
    if (type) {
      delete this.handlers[type];
    } else {
      this.handlers = {};
    }
  }
}

export const eventBus = new EventBus();
