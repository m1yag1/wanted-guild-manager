import { beforeEach, describe, expect, it } from "vitest";
import { createApp } from "../src/app.js";
import { formatStart } from "../src/render.js";
import { STORAGE_KEY } from "../src/storage.js";
import { loadPage, memoryStorage, sequentialIds } from "./helpers.js";

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const cards = () => $$(".event-card");

function fillEventForm({
  title = "Siege night",
  type = "Siege",
  startsAt = "2026-12-05T20:00",
  capacity = "2",
} = {}) {
  const form = $("#event-form");
  form.elements.title.value = title;
  form.elements.type.value = type;
  form.elements.startsAt.value = startsAt;
  form.elements.capacity.value = capacity;
  form.requestSubmit();
}

function signUpOn(card, name, role) {
  const form = $(".signup-form", card);
  form.elements.name.value = name;
  form.elements.role.value = role;
  form.requestSubmit();
}

describe("app", () => {
  let storage;
  let app;

  beforeEach(() => {
    loadPage();
    storage = memoryStorage();
    app = createApp({ doc: document, storage, makeId: sequentialIds() });
  });

  it("fills the event type list and shows an empty state", () => {
    const types = $$("#event-form select[name=type] option").map(
      (o) => o.value,
    );
    expect(types).toEqual([
      "",
      "Siege",
      "Boonstone",
      "Riftstone",
      "Archboss",
      "Guild Raid",
      "Arena",
      "Other",
    ]);
    expect($("#event-list").textContent).toContain("No events yet.");
  });

  it("creates an event, saves it, and resets the form", () => {
    fillEventForm();
    const [card] = cards();
    expect($("h3", card).textContent).toBe("Siege night");
    expect($(".badge", card).textContent).toBe("Siege");
    expect($(".event-meta", card).textContent).toBe(
      `${formatStart(app.getEvents()[0].startsAt)} · 0/2 signed up`,
    );
    expect($(".empty", card).textContent).toBe("No sign ups yet.");
    expect(JSON.parse(storage.getItem(STORAGE_KEY))).toHaveLength(1);
    expect($("#event-form").elements.title.value).toBe("");
    expect($("#event-form-error").hidden).toBe(true);
  });

  it("shows validation errors and creates nothing", () => {
    fillEventForm({ title: "" });
    expect($("#event-form-error").hidden).toBe(false);
    expect($("#event-form-error").textContent).toBe("Title is required.");
    expect(app.getEvents()).toEqual([]);
  });

  it("lists events soonest first", () => {
    fillEventForm({ title: "Later", startsAt: "2026-12-10T20:00" });
    fillEventForm({ title: "Sooner", startsAt: "2026-12-01T20:00" });
    expect(cards().map((c) => $("h3", c).textContent)).toEqual([
      "Sooner",
      "Later",
    ]);
  });

  it("signs members up, counts roles, and disables sign up when full", () => {
    fillEventForm();
    signUpOn(cards()[0], "Kael", "Tank");
    signUpOn(cards()[0], "Mira", "Healer");
    const [card] = cards();
    expect($$(".signup-list li span", card).map((s) => s.textContent)).toEqual([
      "Kael (Tank)",
      "Mira (Healer)",
    ]);
    expect($(".event-roles", card).textContent).toBe(
      "Tank 1 · Healer 1 · DPS 0",
    );
    expect($(".signup-form button", card).disabled).toBe(true);
  });

  it("changes only the event that was signed up for", () => {
    fillEventForm({ title: "First", startsAt: "2026-12-01T20:00" });
    fillEventForm({ title: "Second", startsAt: "2026-12-02T20:00" });
    signUpOn(cards()[1], "Kael", "Tank");
    expect(app.getEvents().map((e) => e.signups.length)).toEqual([0, 1]);
  });

  it("shows sign up errors on that event's card", () => {
    fillEventForm();
    signUpOn(cards()[0], "Kael", "");
    const error = $(".signup-form .form-error", cards()[0]);
    expect(error.hidden).toBe(false);
    expect(error.textContent).toBe("Pick a role.");
  });

  it("withdraws a member and deletes an event", () => {
    fillEventForm();
    signUpOn(cards()[0], "Kael", "Tank");
    $("button[data-action=withdraw]", cards()[0]).click();
    expect(app.getEvents()[0].signups).toEqual([]);
    $("button[data-action=delete]", cards()[0]).click();
    expect(app.getEvents()).toEqual([]);
    expect(JSON.parse(storage.getItem(STORAGE_KEY))).toEqual([]);
  });

  it("ignores clicks that are not on an action button", () => {
    fillEventForm();
    $("h3", cards()[0]).click();
    expect(app.getEvents()).toHaveLength(1);
  });

  it("shows names as text instead of rendering HTML", () => {
    fillEventForm();
    signUpOn(cards()[0], '<img src="x">', "DPS");
    expect($("img", cards()[0])).toBeNull();
    expect($(".signup-list span", cards()[0]).textContent).toBe(
      '<img src="x"> (DPS)',
    );
  });

  it("restores saved events on load", () => {
    fillEventForm();
    loadPage();
    const reloaded = createApp({ doc: document, storage });
    expect(reloaded.getEvents()).toHaveLength(1);
    expect(cards()).toHaveLength(1);
  });
});
