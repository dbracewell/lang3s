import { isKnownType, parseEventMessage } from "@/lib/events/events";
import { eventBus } from "@/lib/events/eventBus";
import { EventSchemas } from "@/lib/events/eventSchemas";

export const TAB_ID = crypto.randomUUID();

const LEADER_KEY = "sse-leader-ts";
const HEARTBEAT_MS = 2_000;
const STALE_AFTER_MS = 6_000;

export const eventChannel = new BroadcastChannel("sse-events");

class EventManager {
  private source: EventSource | null = null;
  private started = false;
  private stopHeartbeat: (() => void) | null = null;
  private leaderWatchId: number | null = null;

  init() {
    if (this.started) return;
    this.started = true;

    this.attachBroadcastListener();

    this.leaderWatchId = window.setInterval(() => {
      this.ensureCorrectRole();
    }, 1_000);

    this.ensureCorrectRole();
  }

  private attachBroadcastListener() {
    if (!!globalThis.__sse_bc_attached) return;
    globalThis.__sse_bc_attached = true;

    eventChannel.onmessage = (evt) => {
      const msg = evt.data as any;
      if (!msg || msg.sender === TAB_ID) return;

      const { type, payload } = msg;
      if (!isKnownType(type)) return;

      const parsed = EventSchemas[type].safeParse(payload);
      if (!parsed.success) return;

      eventBus.emit(type, parsed.data);
    };
  }

  private ensureCorrectRole() {
    // If we already have SSE open, we remain leader (keep heartbeat).
    if (this.source) return;

    // If no active leader, attempt to become it.
    if (this.tryAcquireLeadership()) {
      // We are leader: start heartbeat and SSE exactly once.
      if (!this.stopHeartbeat) this.stopHeartbeat = this.startLeaderHeartbeat();
      this.openSSE();
    }
  }

  private startLeaderHeartbeat(): () => void {
    const id = window.setInterval(() => {
      localStorage.setItem(LEADER_KEY, String(Date.now()));
    }, HEARTBEAT_MS);

    // best-effort cleanup for normal closes
    const onUnload = () => {
      try {
        localStorage.removeItem(LEADER_KEY);
      } catch {}
    };
    window.addEventListener("beforeunload", onUnload);

    return () => {
      clearInterval(id);
      window.removeEventListener("beforeunload", onUnload);
    };
  }

  private tryAcquireLeadership(): boolean {
    const age = this.currentLeaderAgeMs();
    if (age !== null && age < STALE_AFTER_MS) return false;

    localStorage.setItem(LEADER_KEY, String(Date.now()));
    return true;
  }

  private currentLeaderAgeMs(): number | null {
    const v = localStorage.getItem(LEADER_KEY);
    if (!v) return null;
    const ts = Number(v);
    if (Number.isNaN(ts)) return null;
    return Date.now() - ts;
  }

  private openSSE() {
    if (this.source) return;

    const es = new EventSource("/api/realtime");
    this.source = es;

    es.addEventListener("message", (e) => {
      const parsed = parseEventMessage((e as MessageEvent).data);
      if (parsed) {
        eventBus.emit(parsed.type, parsed.data);
        eventChannel.postMessage({
          sender: TAB_ID,
          type: parsed.type,
          payload: parsed.data,
        });
      }
    });

    es.onerror = () => {
      this.closeSSE();
      window.setTimeout(() => {
        this.ensureCorrectRole();
      }, 2_000);
    };
  }

  private closeSSE() {
    if (!this.source) return;
    try {
      this.source.close();
    } catch {}
    this.source = null;
  }

  destroy() {
    this.closeSSE();
    if (this.stopHeartbeat) this.stopHeartbeat();
    this.stopHeartbeat = null;

    if (this.leaderWatchId) clearInterval(this.leaderWatchId);
    this.leaderWatchId = null;

    this.started = false;
  }
}

declare global {
  var __eventManager: EventManager | undefined;
  var __sse_bc_attached: boolean | undefined;
}

export function initEventManager() {
  if (!globalThis.__eventManager) {
    globalThis.__eventManager = new EventManager();
  }
  globalThis.__eventManager.init();
}
