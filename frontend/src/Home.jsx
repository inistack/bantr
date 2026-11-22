import { useEffect } from "react";

import Chat from "./Chat.jsx";
import { useAuth } from "./auth-context.js";
import { socket } from "./socket.js";
import { useConnected } from "./useConnected.js";

function ConnectionBadge() {
  const connected = useConnected();
  return (
    <span className="badge" aria-live="polite">
      {connected ? "● live" : "○ reconnecting…"}
    </span>
  );
}

export default function Home() {
  const { user, logout } = useAuth();

  // One socket for the whole signed-in session: connect on arrival, hang up on sign-out.
  useEffect(() => {
    socket.connect();
    return () => {
      socket.disconnect();
    };
  }, []);

  return (
    <div className="shell">
      <header className="bar">
        <strong>bantr</strong>
        <span>
          <ConnectionBadge />
          Signed in as <strong>{user.name}</strong> <button onClick={logout}>Sign out</button>
        </span>
      </header>
      <Chat />
    </div>
  );
}