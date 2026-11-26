import { useEffect, useState } from "react";

import { socket } from "./socket.js";

const REFRESH_MS = 30000;

export function usePresence(workspaceId) {
  const [state, setState] = useState({ workspaceId: null, online: [] });

  useEffect(() => {
    if (!workspaceId) return;
    let cancelled = false;

    // Asking for the list also subscribes this connection to the workspace's updates.
    function load() {
      socket.emit("presence.list", { workspace_id: workspaceId }, (ack) => {
        if (!cancelled && ack?.ok) setState({ workspaceId, online: ack.online });
      });
    }

    function onUpdate(update) {
      if (update.workspace_id !== workspaceId) return;
      setState((prev) => {
        const others = (prev.workspaceId === workspaceId ? prev.online : []).filter(
          (id) => id !== update.user_id,
        );
        return { workspaceId, online: update.online ? [...others, update.user_id] : others };
      });
    }

    socket.on("presence.update", onUpdate);
    socket.on("connect", load); // after a reconnect the fresh list repairs anything we missed
    if (socket.connected) load();
    const refresh = setInterval(() => {
      if (socket.connected) load();
    }, REFRESH_MS);

    return () => {
      cancelled = true;
      clearInterval(refresh);
      socket.off("presence.update", onUpdate);
      socket.off("connect", load);
    };
  }, [workspaceId]);

  return state.workspaceId === workspaceId ? state.online : [];
}