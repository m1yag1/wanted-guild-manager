import { createApp } from "./app.js";

createApp({ doc: document, storage: window.localStorage });
document.querySelector("#app-version").textContent = __APP_VERSION__;
