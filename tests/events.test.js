import { describe, expect, it } from "vitest";
import {
  MAX_CAPACITY,
  createEvent,
  isFull,
  roleCounts,
  signUp,
  sortByStart,
  validateEvent,
  withdraw,
} from "../src/events.js";

const valid = {
  title: "Siege night",
  type: "Siege",
  startsAt: "2026-12-05T20:00",
  capacity: 2,
};

describe("validateEvent", () => {
  it("accepts a complete event", () => {
    expect(validateEvent(valid)).toEqual([]);
  });

  it("reports every problem at once", () => {
    expect(
      validateEvent({ title: " ", type: "Nope", startsAt: "", capacity: 0 }),
    ).toEqual([
      "Title is required.",
      "Pick an event type.",
      "Pick a valid start time.",
      `Capacity must be a whole number from 1 to ${MAX_CAPACITY}.`,
    ]);
  });

  it.each([1.5, MAX_CAPACITY + 1, Number.NaN])(
    "rejects capacity %s",
    (capacity) => {
      expect(validateEvent({ ...valid, capacity })).toHaveLength(1);
    },
  );

  it("rejects a missing title", () => {
    expect(validateEvent({ ...valid, title: undefined })).toEqual([
      "Title is required.",
    ]);
  });
});

describe("createEvent", () => {
  it("builds a trimmed event with an ISO start and no sign ups", () => {
    const event = createEvent(
      { ...valid, title: "  Siege night  " },
      () => "abc",
    );
    expect(event).toEqual({
      id: "abc",
      title: "Siege night",
      type: "Siege",
      startsAt: new Date("2026-12-05T20:00").toISOString(),
      capacity: 2,
      signups: [],
    });
  });

  it("uses a random id by default", () => {
    expect(createEvent(valid).id).toMatch(/^[0-9a-f-]{36}$/);
  });

  it("throws with the validation messages", () => {
    expect(() => createEvent({ ...valid, title: "" })).toThrow(
      "Title is required.",
    );
  });
});

describe("signUp and withdraw", () => {
  const event = createEvent(valid, () => "e1");

  it("adds a trimmed sign up without changing the original", () => {
    const next = signUp(event, { name: " Kael ", role: "Tank" });
    expect(next.signups).toEqual([{ name: "Kael", role: "Tank" }]);
    expect(event.signups).toEqual([]);
  });

  it("requires a name and a known role", () => {
    expect(() => signUp(event, { name: "", role: "Tank" })).toThrow(
      "Name is required.",
    );
    expect(() => signUp(event, { name: undefined, role: "Tank" })).toThrow(
      "Name is required.",
    );
    expect(() => signUp(event, { name: "Kael", role: "Bard" })).toThrow(
      "Pick a role.",
    );
  });

  it("blocks duplicate names regardless of case", () => {
    const next = signUp(event, { name: "Kael", role: "Tank" });
    expect(() => signUp(next, { name: "kael ", role: "DPS" })).toThrow(
      "Kael is already signed up.",
    );
  });

  it("blocks sign ups once full", () => {
    let next = signUp(event, { name: "A", role: "Tank" });
    expect(isFull(next)).toBe(false);
    next = signUp(next, { name: "B", role: "Healer" });
    expect(isFull(next)).toBe(true);
    expect(() => signUp(next, { name: "C", role: "DPS" })).toThrow(
      "This event is full.",
    );
  });

  it("withdraws by name regardless of case and ignores unknown names", () => {
    const next = signUp(event, { name: "Kael", role: "Tank" });
    expect(withdraw(next, "KAEL").signups).toEqual([]);
    expect(withdraw(next, "Nobody").signups).toHaveLength(1);
  });
});

describe("roleCounts and sortByStart", () => {
  it("counts sign ups per role", () => {
    let event = createEvent({ ...valid, capacity: 5 }, () => "e1");
    event = signUp(event, { name: "A", role: "DPS" });
    event = signUp(event, { name: "B", role: "DPS" });
    event = signUp(event, { name: "C", role: "Healer" });
    expect(roleCounts(event)).toEqual({ Tank: 0, Healer: 1, DPS: 2 });
  });

  it("sorts by start time without mutating the input", () => {
    const late = { id: "late", startsAt: "2026-12-06T00:00:00.000Z" };
    const early = { id: "early", startsAt: "2026-12-01T00:00:00.000Z" };
    const input = [late, early];
    expect(sortByStart(input).map((e) => e.id)).toEqual(["early", "late"]);
    expect(input[0]).toBe(late);
  });
});
