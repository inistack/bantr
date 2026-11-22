import "@testing-library/jest-dom/vitest";
import { beforeEach, vi } from "vitest";

import { socket } from "./socket.js";

// Every test gets a fake socket instead of a real network connection.
vi.mock("./socket.js", async () => {
  const { FakeSocket } = await import("./test-utils.js");
  return { socket: new FakeSocket() };
});

beforeEach(() => socket.reset());