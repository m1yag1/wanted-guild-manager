import { describe, expect, it } from "vitest";
import { STORAGE_KEY, loadEvents, saveEvents } from "../src/storage.js";
import { memoryStorage } from "./helpers.js";

describe("storage", () => {
  it("round-trips events", () => {
    const storage = memoryStorage();
    saveEvents(storage, [{ id: "a" }]);
    expect(loadEvents(storage)).toEqual([{ id: "a" }]);
  });

  it.each([
    ["nothing saved", {}],
    ["corrupt JSON", { [STORAGE_KEY]: "{not json" }],
    ["a non-array value", { [STORAGE_KEY]: '{"id":"a"}' }],
  ])("returns an empty list for %s", (_label, initial) => {
    expect(loadEvents(memoryStorage(initial))).toEqual([]);
  });
});
