import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

import App from "./App.jsx";
import { socket } from "./socket.js";
import { ADA, mockServer } from "./test-utils.js";

const ALPHA = { id: "w1", name: "Alpha", slug: "alpha", role: "owner" };
const GENERAL = { id: "c1", name: "general" };
const BOB = { id: "u2", name: "bob", email: "bob@dev.test", role: "member" };
const CAROL = { id: "u3", name: "carol", email: "carol@dev.test", role: "member" };
const MEMBERS = [{ ...ADA, role: "owner" }, BOB, CAROL];
const msg = (seq, body, user = BOB) => ({
  id: `m${seq}`,
  seq,
  body,
  created_at: "2026-11-11T10:00:00+00:00",
  user: { id: user.id, name: user.name },
});
const typing = (userId, channelId = "c1") => ({ channel_id: channelId, user_id: userId });
const presence = (userId, online, workspaceId = "w1") => ({
  workspace_id: workspaceId,
  user_id: userId,
  online,
});

function setup({ online = ["u1"], presenceList, routes = {} } = {}) {
  socket.responders["channel.join"] = () => ({ ok: true, last_seq: 1 });
  socket.responders["presence.list"] = presenceList ?? (() => ({ ok: true, online }));
  mockServer({
    "GET /auth/me": () => ({ body: ADA }),
    "GET /workspaces": () => ({ body: [ALPHA] }),
    "GET /workspaces/w1/channels": () => ({ body: [GENERAL] }),
    "GET /workspaces/w1/channels/c1/messages": () => ({ body: [msg(1, "hello")] }),
    "GET /workspaces/w1/members": () => ({ body: MEMBERS }),
    ...routes,
  });
  render(<App />);
}

const onlineDots = () => screen.getAllByRole("img", { name: "online" });

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

test("members are listed with their online status, online first", async () => {
  setup({ online: ["u1", "u3"] });
  expect(await screen.findAllByRole("img", { name: "online" })).toHaveLength(2);
  expect(screen.getAllByRole("img", { name: "offline" })).toHaveLength(1);
  const rows = [...document.querySelectorAll(".members li")].map((li) =>
    li.textContent.replace(/[●○\s]/g, ""),
  );
  expect(rows).toEqual(["adaowner", "carolmember", "bobmember"]);
});

test("a presence update flips a member online and back", async () => {
  setup({ online: ["u1"] });
  await screen.findAllByRole("img", { name: "online" });
  act(() => socket.trigger("presence.update", presence("u2", true)));
  expect(onlineDots()).toHaveLength(2);
  act(() => socket.trigger("presence.update", presence("u2", false)));
  expect(onlineDots()).toHaveLength(1);
});

test("presence updates for another workspace are ignored", async () => {
  setup({ online: ["u1"] });
  await screen.findAllByRole("img", { name: "online" });
  act(() => socket.trigger("presence.update", presence("u2", true, "w9")));
  expect(onlineDots()).toHaveLength(1);
});

test("after a reconnect the online list is fetched again", async () => {
  let calls = 0;
  setup({ presenceList: () => ({ ok: true, online: ++calls === 1 ? ["u1"] : ["u1", "u2"] }) });
  await screen.findAllByRole("img", { name: "online" });
  expect(onlineDots()).toHaveLength(1);
  act(() => socket.disconnect());
  act(() => socket.connect());
  await waitFor(() => expect(onlineDots()).toHaveLength(2));
});

test("the typing indicator names who is typing, then expires", async () => {
  setup();
  await screen.findByText("hello");
  await screen.findAllByRole("img", { name: "offline" }); // the member list has loaded
  vi.useFakeTimers();
  act(() => socket.trigger("user.typing", typing("u2")));
  expect(screen.getByText("bob is typing…")).toBeInTheDocument();
  act(() => socket.trigger("user.typing", typing("u3")));
  expect(screen.getByText("bob and carol are typing…")).toBeInTheDocument();
  act(() => vi.advanceTimersByTime(5000));
  expect(screen.queryByText(/typing/)).not.toBeInTheDocument();
});

test("someone's message ends their typing indicator", async () => {
  setup();
  await screen.findAllByRole("img", { name: "offline" });
  act(() => socket.trigger("user.typing", typing("u2")));
  expect(screen.getByText("bob is typing…")).toBeInTheDocument();
  act(() => socket.trigger("message.sent", { channel_id: "c1", message: msg(2, "done typing") }));
  expect(screen.queryByText("bob is typing…")).not.toBeInTheDocument();
  expect(screen.getByText("done typing")).toBeInTheDocument();
});

test("your own typing events are not shown back to you", async () => {
  setup();
  await screen.findByText("hello");
  act(() => socket.trigger("user.typing", typing("u1")));
  expect(screen.queryByText(/typing/)).not.toBeInTheDocument();
});

test("losing the connection clears the typing indicator", async () => {
  setup();
  await screen.findAllByRole("img", { name: "offline" });
  act(() => socket.trigger("user.typing", typing("u2")));
  expect(screen.getByText("bob is typing…")).toBeInTheDocument();
  act(() => socket.disconnect());
  expect(screen.queryByText(/typing/)).not.toBeInTheDocument();
});

test("your own typing is announced, but not on every keystroke", async () => {
  const user = userEvent.setup();
  setup();
  const box = await screen.findByLabelText("Message");
  vi.useFakeTimers({ toFake: ["Date"] }); // control the clock only, so typing still works
  await user.type(box, "hello");
  const announced = () => socket.sent.filter((s) => s.event === "user.typing");
  expect(announced()).toHaveLength(1);
  expect(announced()[0].payload).toEqual({ workspace_id: "w1", channel_id: "c1" });
  vi.setSystemTime(Date.now() + 4000);
  await user.type(box, "!");
  expect(announced()).toHaveLength(2);
});

test("adding a member refreshes the member list", async () => {
  const user = userEvent.setup();
  let loads = 0;
  setup({
    routes: {
      "GET /workspaces/w1/members": () => ({ body: ++loads === 1 ? [{ ...ADA, role: "owner" }] : MEMBERS }),
      "POST /workspaces/w1/members": () => ({
        status: 201,
        body: { id: "u3", email: "carol@dev.test", role: "member" },
      }),
    },
  });
  await user.type(await screen.findByLabelText("Add member by email"), "carol@dev.test");
  await user.click(screen.getByRole("button", { name: "Add member" }));
  expect(await screen.findByText("carol")).toBeInTheDocument();
});