import { useCallback, useEffect, useState } from "react";

import { listMessages } from "./backend.js";
import { channelKey, mergeMessages } from "./messages.js";
import { socket } from "./socket.js";

const emptyState = (key) => ({ key, status: "loading", error: null, messages: [] });

export function useChannelMessages(workspaceId, channelId) {
  const key = channelKey(workspaceId, channelId);
  const [state, setState] = useState(emptyState(null));

  useEffect(() => {
    const myKey = channelKey(workspaceId, channelId);
    let cancelled = false;
    let joined = false; // the server has put us in the room
    let ready = false; // the first history load has finished
    let lastSeq = null; // highest sequence number applied so far

    // Update the state for THIS channel, starting fresh if it still holds another channel's.
    const update = (change) =>
      setState((prev) => {
        const base = prev.key === myKey ? prev : emptyState(myKey);
        return { ...base, ...change(base) };
      });

    function apply(incoming) {
      if (cancelled || incoming.length === 0) return;
      lastSeq = Math.max(lastSeq ?? 0, ...incoming.map((m) => m.seq));
      update((base) => ({ messages: mergeMessages(base.messages, incoming) }));
    }

    function fail(message) {
      if (!cancelled) update(() => ({ status: "error", error: message }));
    }

    // Fetch everything after `cursor`, a page at a time, until nothing is left.
    async function catchUp(cursor) {
      try {
        let from = cursor;
        for (;;) {
          const batch = await listMessages(workspaceId, channelId, { after: from });
          if (cancelled) return;
          apply(batch);
          if (batch.length < 100) return;
          from = batch[batch.length - 1].seq;
        }
      } catch (error) {
        fail(error.message);
      }
    }

    // Subscribe to the channel. Runs on first connect and again after every reconnect.
    function join() {
      const payload = { workspace_id: workspaceId, channel_id: channelId };
      if (lastSeq !== null) payload.after_seq = lastSeq;
      socket.emit("channel.join", payload, async (ack) => {
        if (cancelled) return;
        if (!ack?.ok) {
          fail(ack?.error ?? "Could not join the channel");
          return;
        }
        joined = true;
        try {
          if (ready) {
            // Reconnected: the server returned what we missed while away.
            apply(ack.missed ?? []);
            if (ack.has_more) await catchUp(lastSeq);
          } else {
            // First time: we are subscribed, now load the recent history.
            lastSeq = Math.max(lastSeq ?? 0, ack.last_seq);
            apply(await listMessages(workspaceId, channelId));
            ready = true;
            update(() => ({ status: "ready", error: null }));
          }
        } catch (error) {
          fail(error.message);
        }
      });
    }

    function onMessage({ channel_id: id, message }) {
      if (id !== channelId) return;
      const before = lastSeq;
      const gap = ready && before !== null && message.seq > before + 1;
      apply([message]);
      if (gap) catchUp(before); // sequence numbers are gap-free, so a jump means we missed some
    }

    socket.on("message.sent", onMessage);
    socket.on("connect", join);
    if (socket.connected) join();

    return () => {
      cancelled = true;
      socket.off("message.sent", onMessage);
      socket.off("connect", join);
      if (joined && socket.connected) {
        socket.emit("channel.leave", { workspace_id: workspaceId, channel_id: channelId });
      }
    };
  }, [workspaceId, channelId]);

  // A message we just sent ourselves: show it now. The live copy that follows is a duplicate.
  const addLocal = useCallback(
    (message) =>
      setState((prev) => {
        const base = prev.key === key ? prev : emptyState(key);
        return { ...base, messages: mergeMessages(base.messages, [message]) };
      }),
    [key],
  );

  const current = state.key === key ? state : emptyState(key);
  return { status: current.status, error: current.error, messages: current.messages, addLocal };
}