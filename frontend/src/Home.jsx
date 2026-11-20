import Chat from "./Chat.jsx";
import { useAuth } from "./auth-context.js";

export default function Home() {
  const { user, logout } = useAuth();
  return (
    <div className="shell">
      <header className="bar">
        <strong>bantr</strong>
        <span>
          Signed in as <strong>{user.name}</strong> <button onClick={logout}>Sign out</button>
        </span>
      </header>
      <Chat />
    </div>
  );
}