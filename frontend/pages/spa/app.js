// Point d'entrée unique de la SPA — chargé par dashboard.html (le shell).
// Déclare les routes, démarre le router, monte la sidebar partagée et la
// modale upgrade partagée une seule fois pour toute la session.
import { registerRoute, configure, start } from "./core/router.js";
import { isAuthenticated, setSession, getWorkspaceId, setWorkspaceId } from "./core/state.js";
import { initSidebar, setActiveRoute } from "./sidebar.js";
import { ensureModalLoaded, upgrade } from "./shared/modalUpgrade.js";

import { mount as mountDashboard } from "./views/dashboard.js";
import { mount as mountTransactions } from "./views/transactions.js";
import { mount as mountLiens } from "./views/liens.js";
import { mount as mountApi } from "./views/api.js";
import { mount as mountMultiUsers } from "./views/multiUsers.js";
import { mount as mountProfil } from "./views/profil.js";
import { mount as mountSecurite } from "./views/securite.js";

const WORKSPACE_PLACEHOLDER = "me";

// Atterrissage depuis le callback OAuth Google (backend/routes/users.py:346,
// redirige vers dashboard.html?token=...&workspace_id=...). Traité une seule
// fois, avant le démarrage du router, puis l'URL est réécrite au format
// applicatif propre.
function consumeOAuthBootstrap() {
  const params = new URLSearchParams(window.location.search);
  const urlToken = params.get("token");
  if (!urlToken) return;
  const workspaceId = params.get("workspace_id");
  localStorage.clear();
  setSession({ token: urlToken, workspaceId: workspaceId || undefined });
}

// Normalise l'URL d'entrée vers le schéma applicatif /dash/workspace/{id}/...
// (accès direct au fichier dashboard.html, ou juste après le bootstrap OAuth
// ci-dessus).
function resolveEntryPath() {
  if (!location.pathname.startsWith("/dash/")) {
    const workspaceId = getWorkspaceId() || WORKSPACE_PLACEHOLDER;
    const target = `/dash/workspace/${encodeURIComponent(workspaceId)}/`;
    window.history.replaceState({}, document.title, target);
  }
}

async function init() {
  consumeOAuthBootstrap();

  if (!isAuthenticated()) {
    window.location.href = "/login";
    return;
  }

  resolveEntryPath();

  configure({
    isAuthenticated,
    onUnauthorized: () => {
      window.location.href = "/login";
    },
    onRouteChange: (name, params) => {
      if (params && params.workspaceId && params.workspaceId !== WORKSPACE_PLACEHOLDER) {
        setWorkspaceId(params.workspaceId);
      }
      setActiveRoute(name);
    },
  });

  registerRoute("/dash/workspace/:workspaceId/", mountDashboard, { name: "dashboard" });
  registerRoute("/dash/workspace/:workspaceId/transactions", mountTransactions, { name: "transactions" });
  registerRoute("/dash/workspace/:workspaceId/liens", mountLiens, { name: "liens" });
  registerRoute("/dash/workspace/:workspaceId/api", mountApi, { name: "api" });
  registerRoute("/dash/workspace/:workspaceId/multi-users", mountMultiUsers, { name: "multi-users" });
  registerRoute("/dash/workspace/:workspaceId/profil", mountProfil, { name: "profil" });
  registerRoute("/dash/workspace/:workspaceId/securite", mountSecurite, { name: "securite" });

  await initSidebar();
  await ensureModalLoaded();

  // La modale upgrade partagée (modal-upgrade.html) est chargée une seule
  // fois pour toute la session et reste dans le DOM en permanence — ses
  // boutons de plan (onclick="upgrade('pro')"/"upgrade('business')")
  // doivent donc rester joignables quelle que soit la vue active, y compris
  // Profil/Sécurité qui n'exposent pas leur propre window.upgrade.
  window.upgrade = upgrade;

  start();
}

init();
