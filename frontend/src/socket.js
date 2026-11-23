import { io } from "socket.io-client";

// One connection per browser tab. It stays disconnected until Home asks it to connect, so
// importing this file never touches the network. Same origin (the dev proxy / nginx forwards
// /socket.io) and WebSocket only: no polling fallback, which is what lets the server run
// several processes without sticky sessions.
export const socket = io({ autoConnect: false, transports: ["websocket"] });

// Development only: lets you poke the connection from the browser console, e.g. __socket.disconnect().
if (import.meta.env.DEV) {
  window.__socket = socket;
  socket.on("connect_error", (error) => console.warn("[socket] connect_error:", error.message));
  socket.on("disconnect", (reason) => console.info("[socket] disconnected:", reason));
}