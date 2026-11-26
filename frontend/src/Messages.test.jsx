import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

import App from "./App.jsx";
import { socket } from "./socket.js";
import { ADA, mockServer } from "./test-utils.js";

const ALPHA = { id: "w1", name: "Alpha", slug: "alpha", role: "owner" };
const GENERAL = { id: "c1", name: "general" };
const RANDOM = { id: "c2", name: "random" };
const msg = (seq, body, name = "bob") => ({
  id: `m${seq}`,
  seq,
  body,
  created_at: "2026-11-11T10:00:00+00:00",
  user: { id: "u2", name },
});
const live = (message, channelId = "c1") => ({ channel_id: channelId, message });

function setup({ history = [msg(1, "hello"), msg(2, "world")], join, channels = [GENERAL], routes = {} } = {}) {
  const lastSeq = history.at(-1)?.seq ?? 0;
  socket.responders["channel.join"] = join ?? (() => ({ ok: true, last_seq: lastSeq }));
  mockServer({
    "GET /auth/me": () => ({ body: ADA }),
    "GET /workspaces": () => ({ body: [ALPHA] }),
    "GET /workspaces/w1/channels": () => ({ body: channels }),
    "GET /workspaces/w1/channels/c1/messages": () => ({ body: history }),
    ...routes,
  });
  render(<App />);
}

afterEach(() => vi.unstubAllGlobals());

test("opening a channel joins its room, then shows the recent history", async () => {
  setup();
  expect(await screen.findByText("hello")).toBeInTheDocument();
  expect(screen.getByText("world")).toBeInTheDocument();
  const joins = socket.sent.filter((s) => s.event === "channel.join");
  expect(joins).toEqual([
    { event: "channel.join", payload: { workspace_id: "w1", channel_id: "c1" } },
  ]);
});

test("a live message appears once, even if it is delivered twice", async () => {
  setup();
  await screen.findByText("world");
  act(() => socket.trigger("message.sent", live(msg(3, "live one"))));
  expect(await screen.findByText("live one")).toBeInTheDocument();
  act(() => socket.trigger("message.sent", live(msg(3, "live one"))));
  expect(screen.getAllByText("live one")).toHaveLength(1);
});

test("a message for another channel is ignored", async () => {
  setup();
  await screen.findByText("world");
  act(() => socket.trigger("message.sent", live(msg(3, "elsewhere"), "c2")));
  expect(screen.queryByText("elsewhere")).not.toBeInTheDocument();
});

test("a gap in sequence numbers is filled in from the server", async () => {
  setup({
    routes: {
      "GET /workspaces/w1/channels/c1/messages?after=2&limit=100": () => ({
        body: [msg(3, "three"), msg(4, "four"), msg(5, "five")],
      }),
    },
  });
  await screen.findByText("world");
  act(() => socket.trigger("message.sent", live(msg(5, "five"))));
  expect(await screen.findByText("three")).toBeInTheDocument();
  const bodies = screen.getAllByText(/^(hello|world|three|four|five)$/).map((el) => el.textContent);
  expect(bodies).toEqual(["hello", "world", "three", "four", "five"]);
});

test("after a reconnect the client asks only for what it missed", async () => {
  setup({
    join: (payload) =>
      payload.after_seq === undefined
        ? { ok: true, last_seq: 2 }
        : { ok: true, last_seq: 4, missed: [msg(3, "three"), msg(4, "four")], has_more: false },
  });
  await screen.findByText("world");
  expect(screen.getByText("● live")).toBeInTheDocument();
  act(() => socket.disconnect());
  expect(await screen.findByText("○ reconnecting…")).toBeInTheDocument();
  act(() => socket.connect());
  expect(await screen.findByText("four")).toBeInTheDocument();
  expect(screen.getByText("three")).toBeInTheDocument();
  const joins = socket.sent.filter((s) => s.event === "channel.join");
  expect(joins.at(-1).payload).toEqual({ workspace_id: "w1", channel_id: "c1", after_seq: 2 });
});

test("sending a message shows it straight away and clears the box", async () => {
  const user = userEvent.setup();
  setup({
    routes: {
      "POST /workspaces/w1/channels/c1/messages": (options) => {
        expect(JSON.parse(options.body)).toEqual({ body: "hi there" });
        return { status: 201, body: msg(3, "hi there", "ada") };
      },
    },
  });
  await user.type(await screen.findByLabelText("Message"), "hi there");
  await user.click(screen.getByRole("button", { name: "Send" }));
  expect(await screen.findByText("hi there")).toBeInTheDocument();
  expect(screen.getByLabelText("Message")).toHaveValue("");
});

test("a rate-limit refusal is shown to the sender", async () => {
  const user = userEvent.setup();
  setup({
    routes: {
      "POST /workspaces/w1/channels/c1/messages": () => ({
        status: 429,
        body: { error: "Too many requests. Slow down and retry shortly." },
      }),
    },
  });
  await user.type(await screen.findByLabelText("Message"), "spam");
  await user.click(screen.getByRole("button", { name: "Send" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Too many requests");
});

test("switching channels leaves the old room and joins the new one", async () => {
  const user = userEvent.setup();
  setup({
    channels: [GENERAL, RANDOM],
    routes: { "GET /workspaces/w1/channels/c2/messages": () => ({ body: [msg(1, "over here")] }) },
  });
  await screen.findByText("world");
  await user.click(screen.getByRole("button", { name: "# random" }));
  expect(await screen.findByText("over here")).toBeInTheDocument();
  expect(socket.sent).toContainEqual({
    event: "channel.leave",
    payload: { workspace_id: "w1", channel_id: "c1" },
  });
  expect(socket.sent).toContainEqual({
    event: "channel.join",
    payload: { workspace_id: "w1", channel_id: "c2" },
  });
});

test("message text is shown as text, never run as HTML", async () => {
  setup({ history: [msg(1, "<img src=x onerror=alert(1)>")] });
  expect(await screen.findByText("<img src=x onerror=alert(1)>")).toBeInTheDocument();
  expect(document.querySelector("img")).toBeNull();
});

test("a refused join is reported", async () => {
  setup({ join: () => ({ ok: false, error: "Channel not found" }) });
  expect(await screen.findByRole("alert")).toHaveTextContent("Channel not found");
});