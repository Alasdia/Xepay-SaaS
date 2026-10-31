// Bloc "Équipe & rôles" (mockup de tableau de bord) : actions pilotées par
// le VISITEUR (clics), pas d'automatique. "+ Inviter" ajoute un membre ;
// chaque ligne a 3 icônes : changer de rôle (cycle admin/manager/lecture),
// suspendre (toggle), supprimer.

const ICON_REFRESH = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>`;
const ICON_PAUSE = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>`;
const ICON_TRASH = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path><path d="M10 11v6"></path><path d="M14 11v6"></path><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"></path></svg>`;

const MEMBERS = [
  { initial: "F", name: "Fatou N.", role: "manager" },
  { initial: "I", name: "Ibrahim K.", role: "read" },
  { initial: "L", name: "Laura F.", role: "admin" },
  { initial: "J", name: "John W.", role: "manager" },
  { initial: "M", name: "Mariam T.", role: "read" },
];

const ROLE_LABEL = { admin: "Admin", manager: "Manager", read: "Lecture" };
const ROLE_ORDER = ["admin", "manager", "read"];

function actionsHtml() {
  return `
    <span class="hl-dash-actions">
      <button type="button" class="hl-dash-icon" data-action="status" aria-label="Changer le rôle">${ICON_REFRESH}</button>
      <button type="button" class="hl-dash-icon" data-action="suspend" aria-label="Suspendre">${ICON_PAUSE}</button>
      <button type="button" class="hl-dash-icon" data-action="delete" aria-label="Supprimer">${ICON_TRASH}</button>
    </span>
  `;
}

function rowHtml(member) {
  return `
    <span class="hl-dash-member"><span class="hl-dash-avatar">${member.initial}</span>${member.name}</span>
    <span class="hl-dash-badge hl-dash-badge--${member.role}">${ROLE_LABEL[member.role]}</span>
    ${actionsHtml()}
  `;
}

export function mountTeam(root) {
  const table = root.querySelector("[data-xp-team-table]");
  const inviteBtn = root.querySelector("[data-xp-team-invite]");
  if (!table) return () => {};

  const initialHtml = table.innerHTML;
  const pendingTimeouts = new Set();
  let memberIndex = 0;

  function later(fn, ms) {
    const id = setTimeout(() => {
      pendingTimeouts.delete(id);
      fn();
    }, ms);
    pendingTimeouts.add(id);
  }

  // Les 3 lignes déjà présentes dans le HTML n'ont pas les icônes/data-role :
  // on les complète au montage (progressive enhancement), sans dupliquer le
  // gabarit ailleurs.
  function enhanceRow(row) {
    if (row.classList.contains("hl-dash-row--head") || row.querySelector(".hl-dash-actions")) return;
    const badge = row.querySelector(".hl-dash-badge");
    const role = ROLE_ORDER.find((r) => badge && badge.classList.contains(`hl-dash-badge--${r}`)) || "read";
    row.dataset.role = role;
    row.insertAdjacentHTML("beforeend", actionsHtml());
  }
  Array.from(table.querySelectorAll(".hl-dash-row")).forEach(enhanceRow);

  function addMember() {
    const member = MEMBERS[memberIndex % MEMBERS.length];
    memberIndex++;
    const row = document.createElement("div");
    row.className = "hl-dash-row is-entering is-new";
    row.dataset.role = member.role;
    row.innerHTML = rowHtml(member);
    table.insertBefore(row, table.children[1] || null);
    requestAnimationFrame(() => requestAnimationFrame(() => row.classList.remove("is-entering")));
    later(() => row.classList.remove("is-new"), 900);
  }

  function cycleRole(row) {
    const badge = row.querySelector(".hl-dash-badge");
    if (!badge) return;
    const current = ROLE_ORDER.indexOf(row.dataset.role);
    const next = ROLE_ORDER[(current + 1) % ROLE_ORDER.length];
    row.dataset.role = next;
    badge.className = `hl-dash-badge hl-dash-badge--${next}`;
    badge.textContent = ROLE_LABEL[next];
  }

  function toggleSuspend(row) {
    row.classList.toggle("is-suspended");
  }

  function removeRow(row) {
    row.classList.add("is-leaving");
    later(() => row.remove(), 320);
  }

  function onTableClick(e) {
    const icon = e.target.closest(".hl-dash-icon");
    if (!icon) return;
    const row = icon.closest(".hl-dash-row");
    if (!row || row.classList.contains("hl-dash-row--head")) return;
    const action = icon.dataset.action;
    if (action === "delete") removeRow(row);
    else if (action === "suspend") toggleSuspend(row);
    else if (action === "status") cycleRole(row);
  }

  table.addEventListener("click", onTableClick);
  if (inviteBtn) inviteBtn.addEventListener("click", addMember);

  return function cleanup() {
    table.removeEventListener("click", onTableClick);
    if (inviteBtn) inviteBtn.removeEventListener("click", addMember);
    pendingTimeouts.forEach(clearTimeout);
    pendingTimeouts.clear();
    table.innerHTML = initialHtml;
  };
}
