import { useCallback, useEffect, useState } from "react";

import { listMembers } from "./backend.js";

export function useMembers(workspaceId) {
  const [state, setState] = useState({ workspaceId: null, items: [] });
  const [version, setVersion] = useState(0);

  useEffect(() => {
    if (!workspaceId) return;
    let cancelled = false;
    listMembers(workspaceId)
      .then((items) => {
        if (!cancelled) setState({ workspaceId, items });
      })
      .catch(() => {
        // Without the list, names fall back to "Someone" and the list stays empty.
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId, version]);

  const reload = useCallback(() => setVersion((v) => v + 1), []);
  return { members: state.workspaceId === workspaceId ? state.items : [], reload };
}