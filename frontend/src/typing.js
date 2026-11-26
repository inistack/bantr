export const TYPING_TTL_MS = 5000; // someone counts as typing this long after their last event
export const TYPING_SEND_INTERVAL_MS = 3000; // we announce our own typing at most this often

export function typingText(names) {
  if (names.length === 0) return "";
  if (names.length === 1) return `${names[0]} is typing…`;
  if (names.length === 2) return `${names[0]} and ${names[1]} are typing…`;
  return "Several people are typing…";
}