import { EventType } from "@/lib/events/types";
import { EventPayloadMap } from "@/lib/events/schemas";

type AnyHandler = (payload: unknown) => void;

export class EventBus {
  private handlers: Partial<Record<EventType, Set<AnyHandler>>> = {};

  on<K extends EventType>(
    type: K,
    handler: (payload: EventPayloadMap[K]) => void,
  ): () => void {
    const set = (this.handlers[type] ??= new Set<AnyHandler>());

    const wrapped: AnyHandler = (payload) => {
      handler(payload as EventPayloadMap[K]);
    };

    set.add(wrapped);

    return () => {
      set.delete(wrapped);
      if (set.size === 0) delete this.handlers[type];
    };
  }

  emit<K extends EventType>(type: K, payload: EventPayloadMap[K]) {
    const set = this.handlers[type];
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
