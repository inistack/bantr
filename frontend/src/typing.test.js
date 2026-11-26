import { expect, test } from "vitest";

import { typingText } from "./typing.js";

test.each([
  [[], ""],
  [["bob"], "bob is typing…"],
  [["bob", "carol"], "bob and carol are typing…"],
  [["a", "b", "c"], "Several people are typing…"],
])("typingText(%j) gives %j", (names, expected) => {
  expect(typingText(names)).toBe(expected);
});