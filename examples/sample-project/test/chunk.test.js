const test = require("node:test");
const assert = require("node:assert/strict");
const { chunk } = require("../src/chunk.js");

test("splits an array into even-sized chunks", () => {
  assert.deepEqual(chunk([1, 2, 3, 4, 5, 6], 3), [
    [1, 2, 3],
    [4, 5, 6],
  ]);
});

test("keeps a partial trailing chunk", () => {
  assert.deepEqual(chunk([1, 2, 3, 4, 5, 6, 7], 3), [
    [1, 2, 3],
    [4, 5, 6],
    [7],
  ]);
});

test("returns an empty array for empty input", () => {
  assert.deepEqual(chunk([], 3), []);
});

test("rejects a non-positive chunk size", () => {
  assert.throws(() => chunk([1, 2, 3], 0));
});
