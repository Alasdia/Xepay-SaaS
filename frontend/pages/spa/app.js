// Point d'entrée unique de la SPA — chargé par dashboard.html (le shell).
// Déclare les routes, démarre le router, monte la sidebar partagée et la
// modale upgrade partagée une seule fois pour toute la session.
import { registerRoute, configure, start, navigate } from "./core/router.js";
import { isAuthenticated, setSession, getWorkspaceId, setWorkspaceId } from "./core/state.js";
import { initSidebar, setActiveRoute } from "./sidebar.js";
import { ensureModalLoaded, upgrade } from "./shared/modalUpgrade.js";

import { mount as mountDashboard } from "./views/dashboard.js";
import { mount as mountSolde } from "./views/solde.js";
import { mount as mountTransactions } from "./views/transactions.js";
import { mount as mountLiens } from "./views/liens.js";
import { mount as mountCommerce } from "./views/commerce.js";
import { mount as mountApi } from "./views/api.js";
import { mount as mountMultiUsers } from "./views/multiUsers.js";
import { mount as mountParametres } from "./views/parametres.js";
import { mountPayment as mountPaymentDetail, mountWithdrawal as mountWithdrawalDetail } from "./views/transactionDetail.js";

const WORKSPACE_PLACEHOLDER = "me";

// Atterrissage depuis une redirection serveur qui vient d'établir une
// session — callback OAuth Google (backend/routes/users.py) ou acceptation
// d'invitation (/invites/accept) — via un cookie HttpOnly posé directement
// sur la redirection : plus aucun jeton dans l'URL (migration cookies de
// session, voir audit). Le seul paramètre `workspace_id` suffit à détecter
// cet atterrissage : aucune navigation normale de la SPA ne passe par une
// query string sur dashboard.html (le schéma applicatif utilise
// /dash/workspace/{id}/...). Traité une seule fois, avant le démarrage du
// router, puis l'URL est réécrite au format applicatif propre.
function consumeOAuthBootstrap() {
  const params = new URLSearchParams(window.location.search);
  const workspaceId = params.get("workspace_id");
  if (!workspaceId) return;
  localStorage.clear();
  setSession({ workspaceId });
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
  registerRoute("/dash/workspace/:workspaceId/solde", mountSolde, { name: "solde" });
  // Redirige vers /transactions/paiements plutôt que de monter la vue sur
  // cette URL (l'ancienne vue fusionnée "Toute activité" n'a plus sa propre
  // page) - l'URL affichée doit refléter la page réellement montrée.
  registerRoute(
    "/dash/workspace/:workspaceId/transactions",
    (c, p) => navigate(`/dash/workspace/${encodeURIComponent(p.workspaceId)}/transactions/paiements`, { replace: true }),
    { name: "transactions" }
  );
  // Pages dédiées Paiements/Retraits : même vue/layout que
  // "transactions" (mountTransactions), avec le type verrouillé via un
  // paramètre supplémentaire injecté ici plutôt qu'un chip cliqué en page —
  // chacune n'affiche que son propre contenu, URL directement partageable.
  // Noms de route identiques aux data-page de la sidebar (paiements/
  // retraits, voir sidebar.js) pour que le surlignage actif
  // (setActiveRoute) les reconnaisse directement, sans mapping supplémentaire.
  registerRoute("/dash/workspace/:workspaceId/transactions/paiements", (c, p) => mountTransactions(c, { ...p, fixedType: "payment" }), { name: "paiements" });
  registerRoute("/dash/workspace/:workspaceId/transactions/retraits", (c, p) => mountTransactions(c, { ...p, fixedType: "withdraw" }), { name: "retraits" });
  registerRoute("/dash/workspace/:workspaceId/transactions/paiements/py/:paymentId", mountPaymentDetail, { name: "transaction-paiement-detail" });
  registerRoute("/dash/workspace/:workspaceId/transactions/retraits/wd/:withdrawalId", mountWithdrawalDetail, { name: "transaction-retrait-detail" });
  registerRoute("/dash/workspace/:workspaceId/liens", mountLiens, { name: "liens" });
  // Noms de route identiques aux data-page de la sidebar (clients/produits/
  // ... voir sidebar.html) - avec un préfixe "commerce-" ici, setActiveRoute
  // ne reconnaissait jamais ces routes (comparaison stricte dataset.page ===
  // routeName) et aucun sous-lien Commerce ne s'allumait jamais en "actif".
  registerRoute("/dash/workspace/:workspaceId/commerce/clients", (c, p) => mountCommerce(c, { ...p, section: "clients" }), { name: "clients" });
  registerRoute("/dash/workspace/:workspaceId/commerce/produits", (c, p) => mountCommerce(c, { ...p, section: "produits" }), { name: "produits" });
  registerRoute("/dash/workspace/:workspaceId/commerce/abonnements", (c, p) => mountCommerce(c, { ...p, section: "abonnements" }), { name: "abonnements" });
  registerRoute("/dash/workspace/:workspaceId/commerce/factures", (c, p) => mountCommerce(c, { ...p, section: "factures" }), { name: "factures" });
  registerRoute("/dash/workspace/:workspaceId/commerce/moyens-paiement", (c, p) => mountCommerce(c, { ...p, section: "moyens-paiement" }), { name: "moyens-paiement" });
  registerRoute("/dash/workspace/:workspaceId/commerce/risque", (c, p) => mountCommerce(c, { ...p, section: "risque" }),{ name: "risque" });
  registerRoute("/dash/workspace/:workspaceId/api", mountApi, { name: "api" });
  registerRoute("/dash/workspace/:workspaceId/multi-users", mountMultiUsers, { name: "multi-users" });
  registerRoute("/dash/workspace/:workspaceId/parametres", mountParametres, { name: "parametres" });
  registerRoute("/dash/workspace/:workspaceId/parametres/:section", mountParametres, { name: "parametres-detail" });
  // Anciennes pages dédiées, retirées de la sidebar : leur contenu vit
  // maintenant dans la vue Paramètres (icône ⚙️ du bandeau).
  registerRoute(
    "/dash/workspace/:workspaceId/profil",
    (c, p) => navigate(`/dash/workspace/${encodeURIComponent(p.workspaceId)}/parametres`, { replace: true }),
    { name: "profil" }
  );
  registerRoute(
    "/dash/workspace/:workspaceId/securite",
    (c, p) => navigate(`/dash/workspace/${encodeURIComponent(p.workspaceId)}/parametres`, { replace: true }),
    { name: "securite" }
  );

  await initSidebar();
  await ensureModalLoaded();

  // Icône ⚙️ du bandeau jaune (#top-banner, dashboard.html) - navigue vers
  // la vue Paramètres (ex-pages Profil/KYC + Sécurité, voir
  // views/parametres.js), comme n'importe quel autre lien de la sidebar.
  document.getElementById("settings-gear-btn")?.addEventListener("click", () => {
    navigate(`/dash/workspace/${encodeURIComponent(getWorkspaceId() || WORKSPACE_PLACEHOLDER)}/parametres`);
  });

  // La modale upgrade partagée (modal-upgrade.html) est chargée une seule
  // fois pour toute la session et reste dans le DOM en permanence — ses
  // boutons de plan (onclick="upgrade('pro')"/"upgrade('business')")
  // doivent donc rester joignables quelle que soit la vue active, y compris
  // Profil/Sécurité qui n'exposent pas leur propre window.upgrade.
  window.upgrade = upgrade;

  start();
}

init();
