import { useSyncExternalStore } from "react";

import { socket } from "./socket.js";

function subscribe(onChange) {
  socket.on("connect", onChange);
  socket.on("disconnect", onChange);
  return () => {
    socket.off("connect", onChange);
    socket.off("disconnect", onChange);
  };
}

export function useConnected() {
  return useSyncExternalStore(subscribe, () => socket.connected);
}