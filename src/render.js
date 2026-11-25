// Builds DOM for the event list. Uses textContent everywhere so member names
// and titles can never inject HTML.

import { ROLES, isFull, roleCounts, sortByStart } from "./events.js";

const dateFormat = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

export function formatStart(iso) {
  return dateFormat.format(new Date(iso));
}

function el(doc, tag, props = {}, children = []) {
  const node = doc.createElement(tag);
  Object.assign(node, props);
  node.append(...children);
  return node;
}

export function fillSelect(select, options) {
  const doc = select.ownerDocument;
  select.replaceChildren(
    el(doc, "option", { value: "", textContent: "Choose…" }),
    ...options.map((value) => el(doc, "option", { value, textContent: value })),
  );
}

function renderSignupForm(doc, event) {
  const name = el(doc, "input", {
    name: "name",
    placeholder: "Character name",
    autocomplete: "off",
    required: true,
  });
  name.setAttribute("aria-label", "Character name");
  const role = el(doc, "select", { name: "role", required: true });
  role.setAttribute("aria-label", "Role");
  fillSelect(role, ROLES);
  const error = el(doc, "p", { className: "form-error", hidden: true });
  error.setAttribute("role", "alert");
  const form = el(doc, "form", { className: "signup-form", noValidate: true }, [
    name,
    role,
    el(doc, "button", {
      type: "submit",
      textContent: "Sign up",
      disabled: isFull(event),
    }),
    error,
  ]);
  form.dataset.eventId = event.id;
  return form;
}

function actionButton(doc, label, action, data) {
  const button = el(doc, "button", {
    type: "button",
    className: "link-button",
    textContent: label,
  });
  Object.assign(button.dataset, { action, ...data });
  return button;
}

export function renderEvent(doc, event) {
  const counts = roleCounts(event);
  const summary = ROLES.map((role) => `${role} ${counts[role]}`).join(" · ");
  const signups = event.signups.map((s) =>
    el(doc, "li", {}, [
      el(doc, "span", { textContent: `${s.name} (${s.role})` }),
      actionButton(doc, "Withdraw", "withdraw", {
        eventId: event.id,
        name: s.name,
      }),
    ]),
  );

  const card = el(doc, "li", { className: "event-card" }, [
    el(doc, "header", { className: "event-header" }, [
      el(doc, "h3", { textContent: event.title }),
      el(doc, "span", { className: "badge", textContent: event.type }),
    ]),
    el(doc, "p", { className: "event-meta" }, [
      el(doc, "time", {
        dateTime: event.startsAt,
        textContent: formatStart(event.startsAt),
      }),
      ` · ${event.signups.length}/${event.capacity} signed up`,
    ]),
    el(doc, "p", { className: "event-roles", textContent: summary }),
    signups.length
      ? el(doc, "ul", { className: "signup-list" }, signups)
      : el(doc, "p", { className: "empty", textContent: "No sign ups yet." }),
    renderSignupForm(doc, event),
    actionButton(doc, "Delete event", "delete", { eventId: event.id }),
  ]);
  card.dataset.eventId = event.id;
  return card;
}

export function renderEventList(doc, events) {
  if (!events.length) {
    return [
      el(doc, "li", {
        className: "empty",
        textContent: "No events yet. Create one above.",
      }),
    ];
  }
  return sortByStart(events).map((event) => renderEvent(doc, event));
}
