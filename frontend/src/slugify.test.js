import { expect, test } from "vitest";

import { slugify } from "./slugify.js";

test.each([
  ["Acme Inc", "acme-inc"],
  ["  Design   Team!! ", "design-team"],
  ["Café 2026", "cafe-2026"],
  ["---", ""],
  ["a".repeat(70), "a".repeat(60)],
])("slugify(%j) gives %j", (input, expected) => {
  expect(slugify(input)).toBe(expected);
});