/** @type {Set<MessagePort>} */
const ports = new Set();

let es = null;
let sseUrl = null;

function broadcast(msg) {
  for (const port of ports) {
    try {
      port.postMessage(msg);
    } catch {
      // ignore broken ports
    }
  }
}

function ensureSSE(url) {
  if (es && sseUrl === url) return;

  // Close old
  if (es) {
    try {
      es.close();
    } catch {}
    es = null;
  }

  sseUrl = url;
  es = new EventSource(url);

  es.onopen = () => {
    broadcast({ kind: "status", state: "open" });
  };

  es.onmessage = (e) => {
    broadcast({ kind: "sse", data: e.data });
  };

  es.onerror = () => {
    broadcast({ kind: "status", state: "error" });
    try {
      es.close();
    } catch {}
    es = null;

    // simple backoff reconnect
    setTimeout(() => {
      if (sseUrl) ensureSSE(sseUrl);
    }, 2000);
  };
}

onconnect = (event) => {
  const port = event.ports[0];
  ports.add(port);

  port.start();

  port.postMessage({ kind: "status", state: es ? "open" : "idle" });

  port.onmessage = (msgEvent) => {
    const msg = msgEvent.data;
    if (msg?.kind === "start") {
      ensureSSE(msg.url);
    }
  };

  port.onmessageerror = () => {};

  // Cleanup on tab close
  port.onclose = () => {
    ports.delete(port);
    if (ports.size === 0 && es) {
      try {
        es.close();
      } catch {}
      es = null;
      sseUrl = null;
    }
  };
};
