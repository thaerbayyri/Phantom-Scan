import test from "node:test";
import assert from "node:assert/strict";
import { readStoredFlag, writeStoredFlag, type FlagStorage } from "./stored-flag";

function memoryStorage(initial: Record<string, string> = {}): FlagStorage & { data: Record<string, string> } {
  const data = { ...initial };
  return {
    data,
    getItem: (key) => (key in data ? data[key] : null),
    setItem: (key, value) => {
      data[key] = value;
    },
  };
}

const brokenStorage: FlagStorage = {
  getItem: () => {
    throw new Error("blocked");
  },
  setItem: () => {
    throw new Error("blocked");
  },
};

test("a missing key falls back to the default", () => {
  assert.equal(readStoredFlag(memoryStorage(), "k", true), true);
  assert.equal(readStoredFlag(memoryStorage(), "k", false), false);
});

test("stored values round-trip", () => {
  const storage = memoryStorage();
  writeStoredFlag(storage, "k", false);
  assert.equal(readStoredFlag(storage, "k", true), false);
  writeStoredFlag(storage, "k", true);
  assert.equal(readStoredFlag(storage, "k", false), true);
});

test("an unrecognised stored value falls back to the default", () => {
  assert.equal(readStoredFlag(memoryStorage({ k: "maybe" }), "k", true), true);
});

test("blocked or missing storage never throws and uses the default", () => {
  assert.equal(readStoredFlag(brokenStorage, "k", true), true);
  assert.equal(readStoredFlag(null, "k", false), false);
  assert.doesNotThrow(() => writeStoredFlag(brokenStorage, "k", true));
  assert.doesNotThrow(() => writeStoredFlag(null, "k", true));
});
