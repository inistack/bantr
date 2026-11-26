import { useEffect, useRef, useState } from "react";

import { sendMessage } from "./backend.js";
import { socket } from "./socket.js";
import { TYPING_SEND_INTERVAL_MS, typingText } from "./typing.js";
import { useChannelMessages } from "./useChannelMessages.js";
import { useTyping } from "./useTyping.js";

function formatTime(iso) {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function Messages({ workspaceId, channelId, members = [], selfId }) {
  const { status, error, messages, addLocal } = useChannelMessages(workspaceId, channelId);
  const typingIds = useTyping(workspaceId, channelId, selfId);
  const listRef = useRef(null);
  const stickToBottom = useRef(true);
  const lastTypingSent = useRef(0);
  const [text, setText] = useState("");
  const [sendError, setSendError] = useState(null);
  const [sending, setSending] = useState(false);

  const names = typingIds.map((id) => members.find((m) => m.id === id)?.name ?? "Someone");

  // Follow new messages, unless the reader has scrolled up to read older ones.
  useEffect(() => {
    const list = listRef.current;
    if (list && stickToBottom.current) list.scrollTop = list.scrollHeight;
  }, [messages]);

  function handleScroll(event) {
    const list = event.currentTarget;
    stickToBottom.current = list.scrollHeight - list.scrollTop - list.clientHeight < 40;
  }

  function handleChange(event) {
    const value = event.target.value;
    setText(value);
    const now = Date.now();
    if (value && socket.connected && now - lastTypingSent.current >= TYPING_SEND_INTERVAL_MS) {
      lastTypingSent.current = now;
      socket.emit("user.typing", { workspace_id: workspaceId, channel_id: channelId });
    }
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
      <p className="typing" aria-live="polite">
        {typingText(names) || "\u00a0"}
      </p>
      <form className="compose" onSubmit={handleSubmit}>
        <input
          aria-label="Message"
          value={text}
          onChange={handleChange}
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