import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, api } from "./api.js";
import { AuthContext } from "./auth-context.js";

export function AuthProvider({ children }) {
  const [state, setState] = useState({ status: "loading", user: null });

  // Ask the server who we are. The login cookie is httpOnly, so JavaScript cannot look at it;
  // the server's answer is the only way to know.
  useEffect(() => {
    let cancelled = false;
    api("/auth/me")
      .then((user) => {
        if (!cancelled) setState({ status: "authenticated", user });
      })
      .catch((error) => {
        if (cancelled) return;
        if (error instanceof ApiError && error.status === 401) {
          setState({ status: "anonymous", user: null });
        } else {
          setState({ status: "error", user: null, error: error.message });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const devLogin = useCallback(async (email) => {
    const user = await api("/auth/dev-login", { method: "POST", body: { email } });
    setState({ status: "authenticated", user });
  }, []);

  const logout = useCallback(async () => {
    await api("/auth/logout", { method: "POST" });
    setState({ status: "anonymous", user: null });
  }, []);

  const value = useMemo(() => ({ ...state, devLogin, logout }), [state, devLogin, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}