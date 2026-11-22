import { useEffect, useState } from "react";
import Messages from "./Messages.jsx";

import InlineForm from "./InlineForm.jsx";
import { addMember, createChannel, createWorkspace, listChannels, listWorkspaces } from "./backend.js";
import { slugify } from "./slugify.js";

const CAN_MANAGE = new Set(["owner", "admin"]);

export default function Chat() {
  const [workspaces, setWorkspaces] = useState(null); // null while loading
  const [workspaceId, setWorkspaceId] = useState(null);
  const [channelState, setChannelState] = useState({ workspaceId: null, items: null });
  const [channelId, setChannelId] = useState(null);
  const [loadError, setLoadError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    listWorkspaces()
      .then((items) => {
        if (cancelled) return;
        setWorkspaces(items);
        setWorkspaceId((current) => current ?? items[0]?.id ?? null);
      })
      .catch((error) => {
        if (!cancelled) setLoadError(error.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!workspaceId) return;
    let cancelled = false;
    listChannels(workspaceId)
      .then((items) => {
        if (cancelled) return;
        setChannelState({ workspaceId, items });
        setChannelId((current) =>
          items.some((c) => c.id === current) ? current : (items[0]?.id ?? null),
        );
      })
      .catch((error) => {
        if (!cancelled) setLoadError(error.message);
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  // Derived values: no extra state to keep in sync.
  const workspace = workspaces?.find((w) => w.id === workspaceId) ?? null;
  const channels = channelState.workspaceId === workspaceId ? channelState.items : null;
  const channel = channels?.find((c) => c.id === channelId) ?? null;

  async function handleCreateWorkspace(name) {
    const created = await createWorkspace(name.trim(), slugify(name));
    setWorkspaces((list) => [...list, created]);
    setWorkspaceId(created.id);
  }

  async function handleCreateChannel(name) {
    const created = await createChannel(workspaceId, slugify(name));
    setChannelState((state) => ({ ...state, items: [...state.items, created] }));
    setChannelId(created.id);
  }

  if (loadError) {
    return (
      <p role="alert" className="error">
        {loadError}
      </p>
    );
  }
  if (workspaces === null) {
    return <p>Loading…</p>;
  }

  return (
    <div className="layout">
      <aside className="sidebar">
        <h2>Workspaces</h2>
        <ul>
          {workspaces.map((w) => (
            <li key={w.id}>
              <button className={w.id === workspaceId ? "active" : ""} onClick={() => setWorkspaceId(w.id)}>
                {w.name}
              </button>
            </li>
          ))}
        </ul>
        <InlineForm
          label="New workspace"
          placeholder="Acme Inc"
          submit="Create workspace"
          hint={(value) => value.trim() && `URL name: ${slugify(value)}`}
          onSubmit={handleCreateWorkspace}
        />

        {workspace && (
          <>
            <h2>Channels</h2>
            {channels === null && <p>Loading…</p>}
            {channels?.length === 0 && <p>No channels yet.</p>}
            {channels?.length > 0 && (
              <ul>
                {channels.map((c) => (
                  <li key={c.id}>
                    <button className={c.id === channelId ? "active" : ""} onClick={() => setChannelId(c.id)}>
                      # {c.name}
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {channels !== null && CAN_MANAGE.has(workspace.role) && (
              <>
                <InlineForm
                  label="New channel"
                  placeholder="General"
                  submit="Create channel"
                  hint={(value) => value.trim() && `Channel name: ${slugify(value)}`}
                  onSubmit={handleCreateChannel}
                />
                <InlineForm
                  label="Add member by email"
                  type="email"
                  placeholder="bob@example.com"
                  submit="Add member"
                  successText="Added"
                  onSubmit={(email) => addMember(workspace.id, email.trim().toLowerCase())}
                />
              </>
            )}
          </>
        )}
      </aside>

      <section className="pane">
        {workspace === null && <p>Create a workspace to get started.</p>}
        {workspace && channels && !channel && <p>Select or create a channel.</p>}
                {channel && (
          <>
            <h2># {channel.name}</h2>
            <small>
              {workspace.name} · you are {workspace.role}
            </small>
            <Messages
              key={`${workspace.id}:${channel.id}`}
              workspaceId={workspace.id}
              channelId={channel.id}
            />
          </>
        )}
      </section>
    </div>
  );
}