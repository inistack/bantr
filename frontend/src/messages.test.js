import { expect, test } from "vitest";

import { mergeMessages } from "./messages.js";

const m = (seq, body = `m${seq}`) => ({ seq, body });

test("messages come out ordered by sequence number", () => {
  expect(mergeMessages([m(3), m(1)], [m(2)]).map((x) => x.seq)).toEqual([1, 2, 3]);
});

test("a message that arrives twice is kept once, and the newer copy wins", () => {
  expect(mergeMessages([m(1, "old")], [m(1, "new"), m(1, "new")])).toEqual([m(1, "new")]);
});

test("the inputs are not modified", () => {
  const existing = [m(2)];
  const incoming = [m(1)];
  mergeMessages(existing, incoming);
  expect(existing).toEqual([m(2)]);
  expect(incoming).toEqual([m(1)]);
});