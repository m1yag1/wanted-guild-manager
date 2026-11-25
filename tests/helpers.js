import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const html = readFileSync(
  resolve(import.meta.dirname, "../index.html"),
  "utf8",
);
const body = html.match(/<body>([\s\S]*)<\/body>/)[1];

/** Loads the real page markup into the jsdom document. */
export function loadPage() {
  document.body.innerHTML = body;
}

/** A Storage stand-in backed by a Map. */
export function memoryStorage(initial = {}) {
  const data = new Map(Object.entries(initial));
  return {
    getItem: (key) => (data.has(key) ? data.get(key) : null),
    setItem: (key, value) => data.set(key, String(value)),
  };
}

export function sequentialIds() {
  let n = 0;
  return () => `id-${++n}`;
}
