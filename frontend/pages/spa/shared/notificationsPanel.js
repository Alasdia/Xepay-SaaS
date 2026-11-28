// Centre de notifications (icône cloche, #notifications-btn dans
// #top-banner) — demandé le 2026-11-28 : ce bouton n'était relié à RIEN
// jusqu'ici (un simple showToast statique, voir l'ancien handler dans
// app.js) - confirmé "100% inutilisé" par l'utilisateur. Distinction
// EXPLICITE avec les toasts : un toast est réservé aux actions faites
// DEPUIS le dashboard Xepay (feedback immédiat, éphémère) ; ce panneau
// signale au contraire des évènements survenus AILLEURS (ex. un
// produit/client/commande créé directement sur la boutique Shopify
// connectée) - persistés côté serveur jusqu'à lecture explicite, voir
// backend/models.Notification.
//
// Monté UNE SEULE FOIS par app.js (comme la sidebar/le widget Alhu),
// survit à toute navigation interne.
import { apiFetch } from "../core/apiClient.js";

let panelEl = null;
let listEl = null;
let badgeEl = null;
let toggleBtnEl = null;
let markAllBtnEl = null;

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}

// Format relatif court (pas de dépendance externe type dayjs) - suffit
// largement pour un centre de notifications, jamais besoin d'une
// précision à la seconde au-delà d'une minute.
function formatRelativeTime(isoString) {
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return "";
  const diffSeconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));
  if (diffSeconds < 60) return "à l'instant";
  const diffMinutes = Math.floor(diffSeconds / 60);
  if (diffMinutes < 60) return `il y a ${diffMinutes} min`;
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `il y a ${diffHours} h`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `il y a ${diffDays} j`;
  return date.toLocaleDateString("fr-FR");
}

async function fetchNotifications() {
  const res = await apiFetch("/notifications");
  if (!res.ok) throw new Error("Impossible de récupérer les notifications");
  return res.json();
}

async function fetchUnreadCount() {
  const res = await apiFetch("/notifications/unread-count");
  if (!res.ok) throw new Error("Impossible de récupérer le compteur");
  return res.json();
}

async function markNotificationRead(id) {
  await apiFetch(`/notifications/${encodeURIComponent(id)}/read`, { method: "POST" });
}

async function markAllNotificationsRead() {
  await apiFetch("/notifications/read-all", { method: "POST" });
}

function notificationItemHtml(notification) {
  return `
    <div class="notification-item${notification.read ? "" : " notification-item--unread"}" data-notification-id="${escapeHtml(notification.id)}">
      <div class="notification-item-dot" aria-hidden="true"></div>
      <div class="notification-item-body">
        <div class="notification-item-title">${escapeHtml(notification.title)}</div>
        ${notification.description ? `<div class="notification-item-desc">${escapeHtml(notification.description)}</div>` : ""}
        <div class="notification-item-time">${formatRelativeTime(notification.created_at)}</div>
      </div>
    </div>
  `;
}

async function refreshUnreadBadge() {
  try {
    const { unread_count } = await fetchUnreadCount();
    if (unread_count > 0) {
      badgeEl.textContent = unread_count > 9 ? "9+" : String(unread_count);
      badgeEl.style.display = "flex";
    } else {
      badgeEl.style.display = "none";
    }
  } catch (err) {
    // Silencieux - un échec de comptage ne doit jamais perturber le
    // reste du dashboard (même esprit que les autres badges de ce
    // projet, ex. alhuWidget.js).
  }
}

function positionPanel() {
  const rect = toggleBtnEl.getBoundingClientRect();
  panelEl.style.top = `${rect.bottom + 8}px`;
  panelEl.style.right = `${Math.max(12, window.innerWidth - rect.right - 8)}px`;
}

async function openPanel() {
  positionPanel();
  panelEl.style.display = "flex";
  listEl.innerHTML = `<div class="notification-empty">Chargement...</div>`;
  try {
    const notifications = await fetchNotifications();
    listEl.innerHTML = notifications.length
      ? notifications.map(notificationItemHtml).join("")
      : `<div class="notification-empty">Aucune notification pour le moment.</div>`;
  } catch (err) {
    listEl.innerHTML = `<div class="notification-empty">Erreur de chargement.</div>`;
  }
}

function closePanel() {
  panelEl.style.display = "none";
}

function togglePanel() {
  const willOpen = panelEl.style.display === "none";
  if (willOpen) {
    openPanel();
  } else {
    closePanel();
  }
}

export async function initNotificationsPanel() {
  if (document.getElementById("notifications-panel")) return;
  toggleBtnEl = document.getElementById("notifications-btn");
  if (!toggleBtnEl) return;

  document.body.insertAdjacentHTML(
    "beforeend",
    `
    <div id="notifications-panel" style="display:none;">
      <div id="notifications-panel-header">
        <span>Notifications</span>
        <button type="button" id="notifications-mark-all-read">Tout marquer comme lu</button>
      </div>
      <div id="notifications-panel-list"></div>
    </div>
    `
  );
  panelEl = document.getElementById("notifications-panel");
  listEl = document.getElementById("notifications-panel-list");
  markAllBtnEl = document.getElementById("notifications-mark-all-read");

  // Badge ajouté en JS (jamais dans le HTML statique de dashboard.html,
  // qui ne connaît pas ce module) - même principe que #alhu-widget-badge
  // (shared/alhuWidget.js), positionnement absolu sur un bouton déjà en
  // position relative/fixed dans sa grille flex.
  badgeEl = document.createElement("span");
  badgeEl.id = "notifications-badge";
  badgeEl.style.display = "none";
  toggleBtnEl.appendChild(badgeEl);

  toggleBtnEl.addEventListener("click", (e) => {
    e.stopPropagation();
    togglePanel();
    if (panelEl.style.display !== "none") refreshUnreadBadge();
  });
  markAllBtnEl.addEventListener("click", async (e) => {
    e.stopPropagation();
    await markAllNotificationsRead();
    await openPanel();
    await refreshUnreadBadge();
  });
  // Marque UNE notification comme lue au clic (déléguée sur le
  // conteneur stable #notifications-panel-list, jamais relié
  // individuellement - recréé à chaque ouverture du panneau).
  listEl.addEventListener("click", async (e) => {
    const item = e.target.closest(".notification-item--unread");
    if (!item) return;
    const id = item.dataset.notificationId;
    item.classList.remove("notification-item--unread");
    await markNotificationRead(id);
    await refreshUnreadBadge();
  });
  // Clic en dehors du panneau (et du bouton qui l'ouvre) : ferme -
  // même pattern qu'un menu déroulant classique.
  document.addEventListener("click", (e) => {
    if (panelEl.style.display === "none") return;
    if (panelEl.contains(e.target) || toggleBtnEl.contains(e.target)) return;
    closePanel();
  });

  await refreshUnreadBadge();
}
