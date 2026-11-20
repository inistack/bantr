import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

import App from "./App.jsx";
import { ADA, mockServer } from "./test-utils.js";

const ALPHA = { id: "w1", name: "Alpha", slug: "alpha", role: "owner" };
const BETA = { id: "w2", name: "Beta", slug: "beta", role: "member" };
const signedIn = { "GET /auth/me": () => ({ body: ADA }) };
const general = { "GET /workspaces/w1/channels": () => ({ body: [{ id: "c1", name: "general" }] }) };

afterEach(() => vi.unstubAllGlobals());

test("a new user is invited to create a workspace", async () => {
  mockServer({ ...signedIn, "GET /workspaces": () => ({ body: [] }) });
  render(<App />);
  expect(await screen.findByText("Create a workspace to get started.")).toBeInTheDocument();
});

test("workspaces and their channels are listed, and switching loads the other channels", async () => {
  const user = userEvent.setup();
  mockServer({
    ...signedIn,
    "GET /workspaces": () => ({ body: [ALPHA, BETA] }),
    ...general,
    "GET /workspaces/w2/channels": () => ({ body: [{ id: "c2", name: "random" }] }),
  });
  render(<App />);
  expect(await screen.findByRole("heading", { name: "# general" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Beta" }));
  expect(await screen.findByRole("heading", { name: "# random" })).toBeInTheDocument();
});

test("creating a workspace sends a clean URL name and selects the new workspace", async () => {
  const user = userEvent.setup();
  mockServer({
    ...signedIn,
    "GET /workspaces": () => ({ body: [] }),
    "POST /workspaces": (options) => {
      expect(JSON.parse(options.body)).toEqual({ name: "Acme Inc", slug: "acme-inc" });
      return { status: 201, body: { id: "w3", name: "Acme Inc", slug: "acme-inc", role: "owner" } };
    },
    "GET /workspaces/w3/channels": () => ({ body: [] }),
  });
  render(<App />);
  await user.type(await screen.findByLabelText("New workspace"), "Acme Inc");
  expect(screen.getByText("URL name: acme-inc")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Create workspace" }));
  expect(await screen.findByText("Select or create a channel.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Acme Inc" })).toBeInTheDocument();
});

test("a taken workspace name shows the server's message", async () => {
  const user = userEvent.setup();
  mockServer({
    ...signedIn,
    "GET /workspaces": () => ({ body: [] }),
    "POST /workspaces": () => ({ status: 409, body: { error: "That workspace URL name is already taken" } }),
  });
  render(<App />);
  await user.type(await screen.findByLabelText("New workspace"), "Acme");
  await user.click(screen.getByRole("button", { name: "Create workspace" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("already taken");
});

test("members do not see the channel and member forms", async () => {
  mockServer({
    ...signedIn,
    "GET /workspaces": () => ({ body: [BETA] }),
    "GET /workspaces/w2/channels": () => ({ body: [{ id: "c2", name: "random" }] }),
  });
  render(<App />);
  expect(await screen.findByRole("heading", { name: "# random" })).toBeInTheDocument();
  expect(screen.queryByLabelText("New channel")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Add member by email")).not.toBeInTheDocument();
  expect(screen.getByLabelText("New workspace")).toBeInTheDocument();
});

test("an owner can create a channel, which becomes the selected one", async () => {
  const user = userEvent.setup();
  mockServer({
    ...signedIn,
    "GET /workspaces": () => ({ body: [ALPHA] }),
    ...general,
    "POST /workspaces/w1/channels": (options) => {
      expect(JSON.parse(options.body)).toEqual({ name: "design-team" });
      return { status: 201, body: { id: "c9", name: "design-team", created_at: "t" } };
    },
  });
  render(<App />);
  await user.type(await screen.findByLabelText("New channel"), "Design Team");
  await user.click(screen.getByRole("button", { name: "Create channel" }));
  expect(await screen.findByRole("heading", { name: "# design-team" })).toBeInTheDocument();
});

test("an owner can add a member by email", async () => {
  const user = userEvent.setup();
  mockServer({
    ...signedIn,
    "GET /workspaces": () => ({ body: [ALPHA] }),
    ...general,
    "POST /workspaces/w1/members": (options) => {
      expect(JSON.parse(options.body)).toEqual({ email: "bob@dev.test", role: "member" });
      return { status: 201, body: { id: "u2", email: "bob@dev.test", role: "member" } };
    },
  });
  render(<App />);
  await user.type(await screen.findByLabelText("Add member by email"), "Bob@Dev.test");
  await user.click(screen.getByRole("button", { name: "Add member" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Added");
});

test("adding someone who has not signed up shows the server's message", async () => {
  const user = userEvent.setup();
  mockServer({
    ...signedIn,
    "GET /workspaces": () => ({ body: [ALPHA] }),
    ...general,
    "POST /workspaces/w1/members": () => ({ status: 404, body: { error: "No user with that email" } }),
  });
  render(<App />);
  await user.type(await screen.findByLabelText("Add member by email"), "nobody@dev.test");
  await user.click(screen.getByRole("button", { name: "Add member" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("No user with that email");
});