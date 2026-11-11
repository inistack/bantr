import { AuthProvider } from "./AuthProvider.jsx";
import Home from "./Home.jsx";
import LoginScreen from "./LoginScreen.jsx";
import { useAuth } from "./auth-context.js";

function Gate() {
  const { status, error } = useAuth();
  if (status === "loading") return <p className="center">Loading…</p>;
  if (status === "error") {
    return (
      <p className="center error" role="alert">
        Cannot reach the server: {error}
      </p>
    );
  }
  return status === "authenticated" ? <Home /> : <LoginScreen />;
}

export default function App() {
  return (
    <AuthProvider>
      <Gate />
    </AuthProvider>
  );
}