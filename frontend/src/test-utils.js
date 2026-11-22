import { vi } from "vitest";

export const ADA = { id: "u1", email: "ada@dev.test", name: "ada" };

export const signedOut = () => ({ status: 401, body: { error: "Authentication required" } });

// A tiny fake server: maps "METHOD /path" to a function returning { status, body }.
export function mockServer(routes) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path, options = {}) => {
      const key = `${options.method ?? "GET"} ${path}`;
      const handler = routes[key];
      if (!handler) throw new Error(`unexpected request: ${key}`);
      const { status = 200, body = null } = handler(options);
      return { ok: status < 400, status, statusText: String(status), json: async () => body };
    }),
  );
}

// A stand-in for the Socket.IO client. A test sets `responders` to answer acknowledged emits
// (an emit with no responder is never acknowledged) and calls `trigger` to make the "server"
// send an event.
export class FakeSocket {
  constructor() {
    this.reset();
  }

  reset() {
    this.handlers = new Map();
    this.sent = [];
    this.responders = {};
    this.connected = false;
  }

  on(event, handler) {
    if (!this.handlers.has(event)) this.handlers.set(event, new Set());
    this.handlers.get(event).add(handler);
    return this;
  }

  off(event, handler) {
    this.handlers.get(event)?.delete(handler);
    return this;
  }

  trigger(event, ...args) {
    for (const handler of [...(this.handlers.get(event) ?? [])]) handler(...args);
  }

  connect() {
    this.connected = true;
    this.trigger("connect");
    return this;
  }

  disconnect() {
    this.connected = false;
    this.trigger("disconnect");
    return this;
  }

  emit(event, payload, ack) {
    this.sent.push({ event, payload });
    const respond = this.responders[event];
    if (ack && respond) Promise.resolve().then(() => ack(respond(payload)));
    return this;
  }
}