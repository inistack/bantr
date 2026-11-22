export const channelKey = (workspaceId, channelId) => `${workspaceId}:${channelId}`;

// Combine two lists of messages: unique by sequence number (the newer copy wins), ordered by it.
export function mergeMessages(existing, incoming) {
  const bySeq = new Map(existing.map((message) => [message.seq, message]));
  for (const message of incoming) bySeq.set(message.seq, message);
  return [...bySeq.values()].sort((a, b) => a.seq - b.seq);
}