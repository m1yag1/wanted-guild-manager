import { expect, it } from "vitest";
import { loadPage } from "./helpers.js";

it("boots the app and shows the version", async () => {
  loadPage();
  await import("../src/main.js");
  expect(document.querySelector("#app-version").textContent).toBe(
    __APP_VERSION__,
  );
  expect(document.querySelector("#event-list").textContent).toContain(
    "No events yet.",
  );
});
