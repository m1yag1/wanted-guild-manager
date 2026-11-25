// Wires the page: reads forms, applies event logic, saves, and re-renders.

import { EVENT_TYPES, createEvent, signUp, withdraw } from "./events.js";
import { fillSelect, renderEventList } from "./render.js";
import { loadEvents, saveEvents } from "./storage.js";

function showError(node, message) {
  node.textContent = message;
  node.hidden = !message;
}

export function createApp({ doc, storage, makeId }) {
  const form = doc.querySelector("#event-form");
  const formError = doc.querySelector("#event-form-error");
  const list = doc.querySelector("#event-list");
  let events = loadEvents(storage);

  function render() {
    list.replaceChildren(...renderEventList(doc, events));
  }

  function commit(next) {
    events = next;
    saveEvents(storage, events);
    render();
  }

  function updateEvent(id, change) {
    commit(events.map((event) => (event.id === id ? change(event) : event)));
  }

  fillSelect(form.elements.type, EVENT_TYPES);

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const { title, type, startsAt, capacity } = form.elements;
    try {
      const event = createEvent(
        {
          title: title.value,
          type: type.value,
          startsAt: startsAt.value,
          capacity: Number(capacity.value),
        },
        makeId,
      );
      commit([...events, event]);
      form.reset();
      showError(formError, "");
    } catch (err) {
      showError(formError, err.message);
    }
  });

  list.addEventListener("submit", (e) => {
    e.preventDefault();
    const signupForm = e.target;
    const event = events.find((ev) => ev.id === signupForm.dataset.eventId);
    try {
      const updated = signUp(event, {
        name: signupForm.elements.name.value,
        role: signupForm.elements.role.value,
      });
      updateEvent(event.id, () => updated);
    } catch (err) {
      showError(signupForm.querySelector(".form-error"), err.message);
    }
  });

  list.addEventListener("click", (e) => {
    const button = e.target.closest("button[data-action]");
    if (!button) return;
    const { action, eventId, name } = button.dataset;
    if (action === "withdraw")
      updateEvent(eventId, (event) => withdraw(event, name));
    if (action === "delete")
      commit(events.filter((event) => event.id !== eventId));
  });

  render();
  return { getEvents: () => events };
}
