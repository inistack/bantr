import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

import App from "./App.jsx";

const ADA = { id: "u1", email: "ada@dev.test", name: "ada" };

// A tiny fake server: maps "METHOD /path" to a function returning { status, body }.
function mockServer(routes) {
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

const signedOut = () => ({ status: 401, body: { error: "Authentication required" } });

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.replaceState({}, "", "/");
});

test("an anonymous visitor sees the sign-in screen", async () => {
  mockServer({ "GET /auth/me": signedOut });
  render(<App />);
  expect(await screen.findByText("Sign in with GitHub")).toBeInTheDocument();
});

test("a visitor with a valid session goes straight in", async () => {
  mockServer({ "GET /auth/me": () => ({ body: ADA }) });
  render(<App />);
  expect(await screen.findByText(/Signed in as/)).toBeInTheDocument();
  expect(screen.getByText("ada")).toBeInTheDocument();
});

test("dev login signs in, and sign out returns to the sign-in screen", async () => {
  const user = userEvent.setup();
  mockServer({
    "GET /auth/me": signedOut,
    "POST /auth/dev-login": (options) => {
      expect(JSON.parse(options.body)).toEqual({ email: "ada@dev.test" });
      return { body: ADA };
    },
    "POST /auth/logout": () => ({ body: { status: "logged out" } }),
  });
  render(<App />);
  await user.type(await screen.findByLabelText(/dev login email/i), "ada@dev.test");
  await user.click(screen.getByRole("button", { name: "Dev login" }));
  expect(await screen.findByText(/Signed in as/)).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Sign out" }));
  expect(await screen.findByText("Sign in with GitHub")).toBeInTheDocument();
});

test("a failed GitHub sign-in shows a message and cleans the URL", async () => {
  window.history.replaceState({}, "", "/?login_error=no_verified_email");
  mockServer({ "GET /auth/me": signedOut });
  render(<App />);
  expect(await screen.findByRole("alert")).toHaveTextContent("no verified email");
  expect(window.location.search).toBe("");
});

test("an unreachable server is reported, not mistaken for being signed out", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => {
    throw new TypeError("Failed to fetch");
  }));
  render(<App />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the server");
});