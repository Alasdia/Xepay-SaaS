// Bandeau "il faut une LLC" — étendu à TOUTES les vues/sous-vues le
// 2026-11-27 (demande explicite, remplace la version précédente limitée
// à la vue Accueil, voir git history de spa/views/dashboard.js) : monté
// UNE SEULE FOIS par app.js (comme la sidebar/le widget Alhu), survit à
// toute navigation interne - jamais recréé par une vue individuelle,
// qui écrase #main-content à chaque montage.
//
// Fixé en position, juste sous #top-banner (5vh) - décale dynamiquement
// #sidebar (top/height) et #main-content (margin-top) de sa propre
// hauteur réelle (mesurée, jamais supposée) pour ne jamais les
// recouvrir, même si son contenu varie selon le statut Buildness. Voir
// shared/topBannerStack.js (extrait le 2026-11-27 lors de l'ajout du
// bandeau postLlcOnboardingBanner.js, mutuellement exclusif avec
// celui-ci - jamais visibles en même temps, mais chacun recalcule le
// total à partir de TOUS les bandeaux empilés, pas seulement le sien).
// Jamais masqué/fermable tant que le dossier n'est pas "completed" :
// trop important pour dépendre d'un marchand qui le fermerait une fois
// et l'oublierait.
import { fetchBuildnessStatus } from "./buildnessStatus.js";
import { navigate } from "../core/router.js";
import { getWorkspaceId } from "../core/state.js";
import { applyTopStackOffset, initTopStackResizeListener } from "./topBannerStack.js";

export async function initLlcBanner() {
  if (document.getElementById("llc-required-banner")) return;

  document.body.insertAdjacentHTML(
    "afterbegin",
    `<div id="llc-required-banner" class="top-stack-banner" style="display:none;"></div>`
  );
  initTopStackResizeListener();

  let data;
  try {
    data = await fetchBuildnessStatus();
  } catch (err) {
    applyTopStackOffset(); // Pas de bandeau, mais #sidebar/#main-content doivent quand même être calés sous #top-banner seul.
    return;
  }
  if (data.status === "completed") {
    applyTopStackOffset();
    return;
  }

  const isFailed = data.status === "failed";
  const title = data.status === "not_started"
    ? "Une société américaine (LLC) est nécessaire pour encaisser et retirer vos fonds"
    : isFailed
      ? "La création de votre société américaine (LLC) a échoué"
      : "Votre dossier de création de société américaine (LLC) est en cours";
  const sub = data.status === "not_started"
    ? "Xepay s'appuie sur Stripe Connect, qui exige une société américaine (LLC) et son EIN pour tout marchand non-résident. Sans cette étape, vous ne pourrez ni recevoir de paiements, ni effectuer de retrait."
    : isFailed
      ? "Rendez-vous dans Paramètres > Entreprise pour réessayer - tant qu'elle n'est pas formée, vous ne pourrez ni recevoir de paiements, ni effectuer de retrait."
      : "Suivez son avancement dans \"Mon entreprise\" - tant qu'elle n'est pas formée, vous ne pourrez ni recevoir de paiements, ni effectuer de retrait.";
  const ctaLabel = data.status === "not_started" || isFailed ? "Créer ma société" : "Voir l'avancement";
  const ctaTarget = data.status === "not_started" || isFailed ? "parametres/entreprise" : "mon-entreprise";

  const el = document.getElementById("llc-required-banner");
  el.style.display = "flex";
  el.innerHTML = `
    <div id="llc-required-banner-icon"><i class="fa-solid fa-building-circle-exclamation"></i></div>
    <div id="llc-required-banner-body">
      <div id="llc-required-banner-title">${title}</div>
      <p id="llc-required-banner-sub">${sub}</p>
    </div>
    <button type="button" id="llc-required-banner-cta">${ctaLabel}</button>
  `;
  document.getElementById("llc-required-banner-cta").addEventListener("click", () => {
    navigate(`/dash/workspace/${encodeURIComponent(getWorkspaceId())}/${ctaTarget}`);
  });

  applyTopStackOffset();
}
