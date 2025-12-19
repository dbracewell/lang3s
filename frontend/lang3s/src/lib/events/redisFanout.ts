import { createDisconnectedClient } from "@/lib/redis";

const CHANNEL = "events";

type Listener = (message: string) => void;

class RedisFanout {
  private client = createDisconnectedClient();
  private listeners = new Set<Listener>();
  private ready = false;
  private initializing?: Promise<void>;

  async ensureReady() {
    if (this.ready) return;
    if (this.initializing) return this.initializing;

    this.initializing = (async () => {
      await this.client.connect();

      await this.client.subscribe(CHANNEL, (message) => {
        for (const listener of this.listeners) {
          listener(message);
        }
      });

      this.ready = true;
      console.log("[RedisFanout] subscribed");
    })();

    return this.initializing;
  }

  add(listener: Listener) {
    this.listeners.add(listener);
  }

  remove(listener: Listener) {
    this.listeners.delete(listener);
  }
}

export const redisFanout = new RedisFanout();
