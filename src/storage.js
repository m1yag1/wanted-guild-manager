// Browser storage for events. A server API will replace this in a later phase;
// keeping it behind two functions makes that swap small.

export const STORAGE_KEY = "wgm.events.v1";

export function loadEvents(storage) {
  try {
    const events = JSON.parse(storage.getItem(STORAGE_KEY));
    return Array.isArray(events) ? events : [];
  } catch {
    return [];
  }
}

export function saveEvents(storage, events) {
  storage.setItem(STORAGE_KEY, JSON.stringify(events));
}
