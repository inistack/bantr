import { useEffect, useRef, useState } from "react";

import { sendMessage } from "./backend.js";
import { useChannelMessages } from "./useChannelMessages.js";

function formatTime(iso) {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function Messages({ workspaceId, channelId }) {
  const { status, error, messages, addLocal } = useChannelMessages(workspaceId, channelId);
  const listRef = useRef(null);
  const stickToBottom = useRef(true);
  const [text, setText] = useState("");
  const [sendError, setSendError] = useState(null);
  const [sending, setSending] = useState(false);

  // Follow new messages, unless the reader has scrolled up to read older ones.
  useEffect(() => {
    const list = listRef.current;
    if (list && stickToBottom.current) list.scrollTop = list.scrollHeight;
  }, [messages]);

  function handleScroll(event) {
    const list = event.currentTarget;
    stickToBottom.current = list.scrollHeight - list.scrollTop - list.clientHeight < 40;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const body = text.trim();
    if (!body) return;
    setSending(true);
    setSendError(null);
    try {
      addLocal(await sendMessage(workspaceId, channelId, body));
      setText("");
      stickToBottom.current = true;
    } catch (err) {
      setSendError(err.message);
    } finally {
      setSending(false);
    }
  }

  return (
    <>
      {status === "error" && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {status === "loading" && <p>Loading messages…</p>}
      <ul className="messages" ref={listRef} onScroll={handleScroll} aria-label="Messages">
        {messages.map((m) => (
          <li key={m.seq}>
            <strong>{m.user.name}</strong> <small>{formatTime(m.created_at)}</small>
            <div className="body">{m.body}</div>
          </li>
        ))}
      </ul>
      {status === "ready" && messages.length === 0 && <p>No messages yet. Say hello.</p>}
      <form className="compose" onSubmit={handleSubmit}>
        <input
          aria-label="Message"
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="Write a message"
          maxLength={4000}
        />
        <button type="submit" disabled={sending}>
          Send
        </button>
      </form>
      {sendError && (
        <p role="alert" className="error">
          {sendError}
        </p>
      )}
    </>
  );
}