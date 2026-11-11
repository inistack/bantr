import { useEffect, useState } from "react";

import { useAuth } from "./auth-context.js";

const MESSAGES = {
  provider: "GitHub sign-in failed. Please try again.",
  no_verified_email: "Your GitHub account has no verified email address.",
};

// The backend sends people back here with ?login_error=... when GitHub sign-in fails.
function noticeFromUrl() {
  const code = new URLSearchParams(window.location.search).get("login_error");
  return code ? (MESSAGES[code] ?? "Sign-in failed.") : null;
}

export default function LoginScreen() {
  const { devLogin } = useAuth();
  const [notice, setNotice] = useState(noticeFromUrl);
  const [email, setEmail] = useState("");

  // Tidy the address bar. This updates the browser, not React state.
  useEffect(() => {
    if (new URLSearchParams(window.location.search).has("login_error")) {
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, []);

  async function submitDevLogin(event) {
    event.preventDefault();
    try {
      await devLogin(email);
    } catch (error) {
      setNotice(error.status === 404 ? "Dev login is not enabled on this server." : error.message);
    }
  }

  return (
    <main className="center">
      <h1>bantr</h1>
      {notice && (
        <p role="alert" className="error">
          {notice}
        </p>
      )}
      <a className="button" href="/auth/github/login">
        Sign in with GitHub
      </a>
      {import.meta.env.DEV && (
        <form onSubmit={submitDevLogin}>
          <label>
            Dev login email{" "}
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <button type="submit">Dev login</button>
        </form>
      )}
    </main>
  );
}