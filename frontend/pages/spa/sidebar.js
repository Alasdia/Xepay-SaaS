// Sidebar partagée — montée UNE SEULE FOIS par le shell (dashboard.html),
// jamais démontée pendant la session SPA. Reprend le comportement de
// l'ancien sidebar.js (fetch du fragment, badge plan, hamburger mobile,
// logout) en l'adaptant à la navigation SPA : les liens du menu ne
// rechargent plus la page (router.navigate) et pointent déjà vers le futur
// schéma /dash/workspace/{workspace_id}/....

import { apiFetch } from "./core/apiClient.js";
import { getWorkspaceId, clearSession, setPlan } from "./core/state.js";
import { navigate } from "./core/router.js";
import { showUpgradeModal } from "./shared/modalUpgrade.js";

// data-page (déjà présent dans sidebar.html) -> segment de route SPA
const ROUTE_BY_PAGE = {
  dashboard: "",
  transactions: "transactions",
  paiements: "transactions/paiements",
  retraits: "transactions/retraits",
  transferts: "transactions/transferts",

  liens: "liens",

  clients: "commerce/clients",
  produits: "commerce/produits",
  abonnements: "commerce/abonnements",
  factures: "commerce/factures",
  "moyens-paiement": "commerce/moyens-paiement",
  risque: "commerce/risque",

  api: "api",
  "multi-users": "multi-users",
  profile: "profil",
  securité: "securite",
};

function routeFor(pageKey) {
  const workspaceId = getWorkspaceId() || "me";
  const segment = ROUTE_BY_PAGE[pageKey] ?? "";
  return `/dash/workspace/${encodeURIComponent(workspaceId)}/${segment}`;
}

// Glyphe dédié (fa-chevron-down) plutôt qu'une rotation CSS de
// fa-chevron-right, pour un rendu fidèle au "^ renversé" demandé — partagé
// entre le clic sur le chevron, le clic sur "Transactions" et l'ouverture
// automatique à l'arrivée directe sur une sous-route (setActiveRoute).
function setSubmenuOpen(submenuId, isOpen) {
  const submenu = document.getElementById(submenuId);
  const toggleBtn = document.querySelector(`[data-submenu-toggle="${submenuId}"]`);
  if (!submenu) return;
  submenu.classList.toggle("open", isOpen);
  toggleBtn?.setAttribute("aria-expanded", String(isOpen));
  const icon = toggleBtn?.querySelector("i");
  icon?.classList.toggle("fa-chevron-right", !isOpen);
  icon?.classList.toggle("fa-chevron-down", isOpen);
}

function toggleSubmenu(submenuId) {
  const submenu = document.getElementById(submenuId);
  if (!submenu) return;
  setSubmenuOpen(submenuId, !submenu.classList.contains("open"));
}

export async function initSidebar() {
  const container = document.getElementById("sidebar-container");
  if (!container) return;
  container.innerHTML = await fetch("/sidebar.html", { cache: "no-store" }).then((r) => r.text());

  container.querySelectorAll("a[data-page]").forEach((a) => {
    a.setAttribute("data-route", routeFor(a.dataset.page));
    a.setAttribute("href", routeFor(a.dataset.page));
  });
  const commerceTitle = container.querySelector(".commerce-title");
  if (commerceTitle) {
    commerceTitle.addEventListener("click", () => {
      setSubmenuOpen("submenu-commerce", true);
      navigate(routeFor("clients"));
    });
  }
  container.addEventListener("click", (e) => {
    const link = e.target.closest("a[data-route]");
    if (!link) return;
    // "Transactions" : les 3 sous-vues (Paiements/Retraits/Transferts)
    // couvrent désormais tout ce que cette page "Toute activité" affichait
    // seule — son clic ouvre donc le sous-menu, comme le chevron, au lieu
    // de naviguer (la route /transactions reste joignable par URL directe).
    if (link.dataset.page === "transactions") {
      e.preventDefault();
      toggleSubmenu("submenu-transactions");
      return;
    }
    e.preventDefault();
    navigate(link.getAttribute("data-route"));
  });

  // Sous-pages (ex: Paiements/Retraits/Transferts sous Transactions) :
  // masquées par défaut, affichées uniquement au clic sur l'icône de
  // déroulement associée (bouton sans data-route, jamais intercepté par le
  // handler de navigation ci-dessus) — ou sur le lien "Transactions" lui-même.
  container.querySelectorAll("[data-submenu-toggle]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      toggleSubmenu(btn.dataset.submenuToggle);
    });
  });

  await loadUser();

  container.querySelectorAll(".upgrade-btn").forEach((btn) =>
    btn.addEventListener("click", () => showUpgradeModal())
  );

  setupHamburger(container);

  // Référencées par des onclick= inline dans sidebar.html — exposées une
  // fois pour toute la durée de vie de l'app (la sidebar n'est jamais
  // démontée pendant la session).
  window.logout = logout;
  window.checkApiAccess = checkApiAccess;
  window.checkMultiUsersAccess = checkMultiUsersAccess;
}

// Routes de détail -> route de section dont elles doivent garder le
// highlight actif dans la sidebar (ex: le détail d'un paiement reste sous
// "Transactions", le détail d'un lien reste sous "Liens").
const DETAIL_ROUTE_PARENT = {
  "transaction-paiement-detail": "transactions",
  "transaction-retrait-detail": "transactions",
  "lien-detail": "liens",
};

export function setActiveRoute(routeName) {
  const effectiveRouteName = DETAIL_ROUTE_PARENT[routeName] || routeName;
  document.querySelectorAll("#sidebar a[data-page]").forEach((a) => {
    const mapped = a.dataset.page === "dashboard" ? "dashboard" : a.dataset.page === "profile" ? "profil" : a.dataset.page === "securité" ? "securite" : a.dataset.page;
    a.classList.toggle("active-link", mapped === effectiveRouteName);
  });
  // Arrivée directe sur une URL dédiée (/transactions/paiements|retraits|
  // transferts, ex: lien partagé ou favori) : déplie le sous-menu pour que
  // le sous-lien actif ci-dessus soit visible, pas seulement surligné.
  if (["paiements", "retraits", "transferts"].includes(effectiveRouteName)) {
    setSubmenuOpen("submenu-transactions", true);
  }
  // Les liens du menu doivent toujours pointer vers le workspace courant,
  // même après un changement de workspace en cours de session.
  document.querySelectorAll("#sidebar a[data-page]").forEach((a) => {
    const href = routeFor(a.dataset.page);
    a.setAttribute("data-route", href);
    a.setAttribute("href", href);
  });
}

// Exposée pour les vues qui doivent rafraîchir le badge de plan partagé de
// la sidebar après un changement de workspace (dashboard, multi-users —
// dans l'ancien MPA elles ciblaient directement #badge-plan par ID, qui
// vit physiquement dans le fragment sidebar.html).
export async function refreshPlanBadge() {
  return loadUser();
}

async function loadUser() {
  try {
    const res = await apiFetch("/me/user-plan");
    const user = await res.json();
    window.GLOBAL_PLAN = user;
    setPlan(user.plan);
    updatePlanUI(user.plan);
  } catch (err) {
    console.error("ERREUR loadUser (sidebar):", err);
  }
}

function updatePlanUI(plan) {
  const badge = document.getElementById("badge-plan");
  if (!badge) return;
  badge.className = "badge " + plan;
  badge.textContent = plan.toUpperCase();
}

function logout() {
  clearSession();
  window.location.href = "/login";
}

function checkApiAccess() {
  const plan = window.GLOBAL_PLAN?.plan;
  if (plan === "free") sessionStorage.setItem("openApiUpgrade", "true");
}

function checkMultiUsersAccess() {
  const plan = window.GLOBAL_PLAN?.plan;
  if (plan !== "business") sessionStorage.setItem("openMultiUsersUpgrade", "true");
}

function setupHamburger(root) {
  const sidebar = root.querySelector("#sidebar");
  if (!sidebar || sidebar.dataset.hamburgerBound) return;
  sidebar.dataset.hamburgerBound = "true";
  const overlay = document.createElement("div");
  overlay.className = "sidebar-overlay";
  document.body.appendChild(overlay);
  const btn = document.createElement("button");
  btn.className = "dash-hamburger";
  btn.innerHTML = "<span></span><span></span><span></span>";
  document.body.appendChild(btn);
  const open = () => {
    sidebar.classList.add("open");
    overlay.classList.add("active");
    btn.classList.add("open");
    document.body.style.overflow = "hidden";
  };
  const close = () => {
    sidebar.classList.remove("open");
    overlay.classList.remove("active");
    btn.classList.remove("open");
    document.body.style.overflow = "";
  };
  btn.addEventListener("click", () => (sidebar.classList.contains("open") ? close() : open()));
  overlay.addEventListener("click", close);
  sidebar.querySelectorAll("a").forEach((a) => a.addEventListener("click", close));
}
