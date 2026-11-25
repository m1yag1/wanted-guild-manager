// Pure event and sign-up logic. No DOM, no storage: easy to test and reuse
// later on a server or in a Discord bot.

export const EVENT_TYPES = [
  "Siege",
  "Boonstone",
  "Riftstone",
  "Archboss",
  "Guild Raid",
  "Arena",
  "Other",
];

export const ROLES = ["Tank", "Healer", "DPS"];

export const MAX_CAPACITY = 100;

function randomId() {
  return crypto.randomUUID();
}

/** Returns a list of human-readable problems with the event input. Empty means valid. */
export function validateEvent({ title, type, startsAt, capacity }) {
  const errors = [];
  if (!title || !title.trim()) errors.push("Title is required.");
  if (!EVENT_TYPES.includes(type)) errors.push("Pick an event type.");
  if (Number.isNaN(Date.parse(startsAt)))
    errors.push("Pick a valid start time.");
  if (!Number.isInteger(capacity) || capacity < 1 || capacity > MAX_CAPACITY) {
    errors.push(`Capacity must be a whole number from 1 to ${MAX_CAPACITY}.`);
  }
  return errors;
}

export function createEvent(input, makeId = randomId) {
  const errors = validateEvent(input);
  if (errors.length) throw new Error(errors.join(" "));
  return {
    id: makeId(),
    title: input.title.trim(),
    type: input.type,
    startsAt: new Date(input.startsAt).toISOString(),
    capacity: input.capacity,
    signups: [],
  };
}

function sameName(a, b) {
  return a.trim().toLowerCase() === b.trim().toLowerCase();
}

export function isFull(event) {
  return event.signups.length >= event.capacity;
}

/** Returns a new event with the member signed up. Throws if the sign-up is not allowed. */
export function signUp(event, { name, role }) {
  if (!name || !name.trim()) throw new Error("Name is required.");
  if (!ROLES.includes(role)) throw new Error("Pick a role.");
  const existing = event.signups.find((s) => sameName(s.name, name));
  if (existing) throw new Error(`${existing.name} is already signed up.`);
  if (isFull(event)) throw new Error("This event is full.");
  return { ...event, signups: [...event.signups, { name: name.trim(), role }] };
}

/** Returns a new event without the named member. Unknown names are ignored. */
export function withdraw(event, name) {
  return {
    ...event,
    signups: event.signups.filter((s) => !sameName(s.name, name)),
  };
}

export function roleCounts(event) {
  const counts = Object.fromEntries(ROLES.map((role) => [role, 0]));
  for (const signup of event.signups) counts[signup.role] += 1;
  return counts;
}

export function sortByStart(events) {
  return [...events].sort(
    (a, b) => Date.parse(a.startsAt) - Date.parse(b.startsAt),
  );
}
