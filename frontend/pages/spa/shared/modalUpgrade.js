// Modale "upgrade" partagée — remplace les 7 copies dupliquées de
// showUpgradeModal/updateUpgradeModal/upgrade(). Chargée une seule fois par
// le shell (persistante, jamais démontée), au lieu d'être ré-injectée à
// chaque page comme avant (modal-upgrade.js d'origine).
//
// Seule la variante "commune" (dashboard/profil/sécurité/transactions,
// identiques à l'origine) est consolidée ici. liens.js (source du plan =
// window.GLOBAL_PLAN au lieu de localStorage), API.js (feature "API.html"
// + logique inline) et multi-users.js (animation reveal différente, pas
// d'appel à updateUpgradeModal) avaient un comportement visuel/logique
// différent dans le code d'origine : leurs variantes restent locales à
// leur propre vue pour ne rien changer à l'existant.

import { apiFetch } from "../core/apiClient.js";
import { getPlan } from "../core/state.js";

let loaded = false;

export async function ensureModalLoaded() {
  if (loaded || document.getElementById("modalUpgrade")) {
    loaded = true;
    return;
  }
  try {
    const html = await fetch("/modal-upgrade.html").then((r) => r.text());
    document.body.insertAdjacentHTML("beforeend", html);
    loaded = true;
    document.getElementById("modalUpgrade")?.addEventListener("shown.bs.modal", () => {
      document.querySelectorAll("#modalUpgrade .reveal").forEach((el, index) => {
        setTimeout(() => el.classList.add("visible"), index * 100);
      });
    });
  } catch (err) {
    console.error("Erreur chargement modal upgrade:", err);
  }
}

export function updateUpgradeModal(plan, feature) {
  document.querySelectorAll(".plan-card").forEach((card) => card.classList.remove("plan-disabled"));
  if (feature === "multi-users") {
    document.querySelector(".plan-starter")?.classList.add("plan-disabled");
    document.querySelector(".plan-pro")?.classList.add("plan-disabled");
    return;
  }
  if (plan === "free") document.querySelector(".plan-starter")?.classList.add("plan-disabled");
  if (plan === "pro") document.querySelector(".plan-pro")?.classList.add("plan-disabled");
  if (plan === "business") document.querySelector(".plan-business")?.classList.add("plan-disabled");
}

export function showUpgradeModal(feature = null) {
  const plan = getPlan();
  updateUpgradeModal(plan, feature);
  const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById("modalUpgrade"));
  modal.show();
}

export async function upgrade(plan) {
  const res = await apiFetch("/create-checkout-session", {
    method: "POST",
    body: { plan },
  });
  const data = await res.json();
  if (!res.ok || !data.url) {
    alert("Erreur lors de l'ouverture de Stripe");
    return;
  }
  window.location.href = data.url;
}
