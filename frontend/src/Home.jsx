import { useAuth } from "./auth-context.js";

export default function Home() {
  const { user, logout } = useAuth();
  return (
    <main>
      <header className="bar">
        <span>
          Signed in as <strong>{user.name}</strong>
        </span>
        <button onClick={logout}>Sign out</button>
      </header>
      <p>Workspaces and channels arrive in the next step.</p>
    </main>
  );
}