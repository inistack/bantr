import { useEffect, useState } from "react";

import { channelKey } from "./messages.js";
import { socket } from "./socket.js";
import { TYPING_TTL_MS } from "./typing.js";

// Ids of the people currently typing in this channel (never including ourselves).
export function useTyping(workspaceId, channelId, selfId) {
  const key = channelKey(workspaceId, channelId);
  const [state, setState] = useState({ key: null, ids: [] });

  useEffect(() => {
    const myKey = channelKey(workspaceId, channelId);
    const timers = new Map(); // user id -> the timeout that will end their "typing"

    const setIds = (change) =>
      setState((prev) => ({ key: myKey, ids: change(prev.key === myKey ? prev.ids : []) }));

    function stop(userId) {
      clearTimeout(timers.get(userId));
      timers.delete(userId);
      setIds((ids) => ids.filter((id) => id !== userId));
    }

    function stopAll() {
      timers.forEach((timer) => clearTimeout(timer));
      timers.clear();
      setIds(() => []);
    }

    function onTyping({ channel_id: id, user_id: userId }) {
      if (id !== channelId || userId === selfId) return;
      clearTimeout(timers.get(userId));
      timers.set(userId, setTimeout(() => stop(userId), TYPING_TTL_MS));
      setIds((ids) => (ids.includes(userId) ? ids : [...ids, userId]));
    }

    function onMessage({ channel_id: id, message }) {
      if (id === channelId) stop(message.user.id); // they sent it, so they are done typing
    }

    socket.on("user.typing", onTyping);
    socket.on("message.sent", onMessage);
    socket.on("disconnect", stopAll); // a dropped connection leaves nothing to trust
    return () => {
      socket.off("user.typing", onTyping);
      socket.off("message.sent", onMessage);
      socket.off("disconnect", stopAll);
      timers.forEach((timer) => clearTimeout(timer));
    };
  }, [workspaceId, channelId, selfId]);

  return state.key === key ? state.ids : [];
}