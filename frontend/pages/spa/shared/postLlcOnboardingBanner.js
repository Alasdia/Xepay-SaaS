// Bandeau "prochaine étape d'activation" — demande du 2026-11-27 :
// "lorsqu'il crée sa LLC, est-ce qu'il y a une alerte qui lui dit les
// onboardings qu'il doit faire pour commencer à recevoir les paiements
// de ses clients... et pour activer les retraits de ses fonds vers son
// compte bancaire local UEMOA ?" - avant ce chantier, la réponse était
// non : une fois la LLC formée, le bandeau llcBanner.js disparaît et
// rien ne prend le relais.
//
// Mutuellement exclusif avec llcBanner.js (celui-ci exige Buildness
// "completed", l'autre son contraire) - jamais visibles en même temps,
// mais partage son créneau (juste sous #top-banner) et le même
// mécanisme d'offset partagé (voir shared/topBannerStack.js).
//
// 3 étapes SÉQUENTIELLES, dans l'ordre métier confirmé par l'utilisateur
// le 2026-11-27 (jamais Stripe Connect en premier) :
//   1. Récupérer les coordonnées bancaires USD du wallet Verto (GET
//      /verto/status -> usd_account_number) - c'est CE compte qui sert
//      de destination de payout externe à Stripe (Stripe interdit à la
//      plateforme de le faire à sa place, voir models.py).
//   2. Ajouter ce compte USD dans le Dashboard Stripe Express pour
//      activer l'encaissement ET le virement (GET /stripe/status ->
//      charges_enabled && payouts_enabled).
//   3. Enregistrer la destination finale, locale UEMOA, dans Verto
//      (GET /verto/status -> beneficiary_registered) - dernière étape
//      avant de pouvoir réellement déclencher un retrait.
//
// Aligné avec le partenariat Verto encore en cours de finalisation
// (2026-11-27) : construit dès maintenant (UI/UX de la colonne
// vertébrale "payout UEMOA" du produit), indépendamment de
// VERTO_ENABLED - ce flag ne bloque que les actions d'ÉCRITURE
// (routes/verto.py), jamais GET /verto/status, lu ici en lecture seule.
import { fetchBuildnessStatus } from "./buildnessStatus.js";
import { apiFetch } from "../core/apiClient.js";
import { navigate } from "../core/router.js";
import { getWorkspaceId } from "../core/state.js";
import { applyTopStackOffset, initTopStackResizeListener } from "./topBannerStack.js";

const STEPS = {
  verto: {
    icon: "fa-solid fa-building-columns",
    title: "Récupérez vos coordonnées bancaires USD",
    sub: "Avant d'activer Stripe Connect, générez le compte bancaire USD dédié (Verto) qui servira de destination à vos virements Stripe - c'est ce compte que vous ajouterez ensuite dans votre Dashboard Stripe Express.",
    ctaLabel: "Récupérer mes coordonnées",
    ctaTarget: "parametres/retraits",
  },
  stripe: {
    icon: "fa-brands fa-stripe",
    title: "Activez votre compte Stripe Connect",
    sub: "Ajoutez votre compte bancaire USD dans votre Dashboard Stripe Express et complétez votre vérification d'identité pour commencer à encaisser les paiements de vos clients et activer vos virements.",
    ctaLabel: "Activer Stripe Connect",
    ctaTarget: "parametres/stripe",
  },
  uemoa: {
    icon: "fa-solid fa-money-bill-transfer",
    title: "Enregistrez votre compte bancaire local",
    sub: "Dernière étape : enregistrez votre compte bancaire local (Bénin, Burkina Faso, Côte d'Ivoire, Niger, Sénégal ou Togo) pour pouvoir retirer vos fonds vers votre banque.",
    ctaLabel: "Enregistrer mon compte local",
    ctaTarget: "parametres/retraits",
  },
};

// Lecture seule, 3 appels indépendants (jamais un seul "état global"
// côté serveur) - tolère qu'un seul des 3 échoue (ex. rôle insuffisant
// pour /verto/status, réservé au propriétaire du workspace, voir
// permission_service.CAPABILITY_DEFAULTS["manage_stripe_account_config"])
// en masquant alors tout le bandeau : un non-owner ne peut agir sur
// aucune de ces 3 étapes, aucune raison de l'en notifier.
async function fetchOnboardingState() {
  const [buildnessRes, stripeRes, vertoRes] = await Promise.all([
    apiFetch(`/buildness/status/${encodeURIComponent(getWorkspaceId())}`),
    apiFetch("/stripe/status"),
    apiFetch("/verto/status"),
  ]);
  if (!buildnessRes.ok || !stripeRes.ok || !vertoRes.ok) {
    throw new Error("Statut d'onboarding indisponible.");
  }
  const [buildness, stripe, verto] = await Promise.all([
    buildnessRes.json(),
    stripeRes.json(),
    vertoRes.json(),
  ]);
  return { buildness, stripe, verto };
}

function nextStepKey({ buildness, stripe, verto }) {
  if (buildness.status !== "completed") return null; // Pris en charge par llcBanner.js.
  if (!verto.usd_account_number) return "verto";
  const stripeReady = Boolean(stripe.stripe && stripe.stripe.charges_enabled && stripe.stripe.payouts_enabled);
  if (!stripeReady) return "stripe";
  if (!verto.beneficiary_registered) return "uemoa";
  return null; // Les 3 étapes sont terminées - plus rien à afficher.
}

export async function initPostLlcOnboardingBanner() {
  if (document.getElementById("post-llc-onboarding-banner")) return;

  document.body.insertAdjacentHTML(
    "afterbegin",
    `<div id="post-llc-onboarding-banner" class="top-stack-banner" style="display:none;"></div>`
  );
  initTopStackResizeListener();

  let state;
  try {
    state = await fetchOnboardingState();
  } catch (err) {
    applyTopStackOffset();
    return;
  }

  const key = nextStepKey(state);
  if (!key) {
    applyTopStackOffset();
    return;
  }

  const step = STEPS[key];
  const el = document.getElementById("post-llc-onboarding-banner");
  el.style.display = "flex";
  el.innerHTML = `
    <div id="post-llc-onboarding-banner-icon"><i class="${step.icon}"></i></div>
    <div id="post-llc-onboarding-banner-body">
      <div id="post-llc-onboarding-banner-title">${step.title}</div>
      <p id="post-llc-onboarding-banner-sub">${step.sub}</p>
    </div>
    <button type="button" id="post-llc-onboarding-banner-cta">${step.ctaLabel}</button>
  `;
  document.getElementById("post-llc-onboarding-banner-cta").addEventListener("click", () => {
    navigate(`/dash/workspace/${encodeURIComponent(getWorkspaceId())}/${step.ctaTarget}`);
  });

  applyTopStackOffset();
}
