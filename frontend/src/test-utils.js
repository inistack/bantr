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