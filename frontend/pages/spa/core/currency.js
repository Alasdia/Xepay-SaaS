// Devise d'affichage préférée de l'utilisateur, partagée par toute la SPA.
// Un seul sélecteur existe (vue Accueil, bloc "Votre aperçu", voir
// views/dashboard.js) : il ÉCRIT cette préférence via setCurrency, toutes
// les autres vues se contentent de la LIRE au montage (getCurrency) pour
// convertir leurs propres totaux - jamais de sélecteur dupliqué ailleurs.
// Persisté en localStorage comme le reste de l'état non sensible (voir
// core/state.js) : un changement de devise survit à la navigation et aux
// rechargements, sans jamais être réinitialisé à la déconnexion (c'est une
// préférence d'affichage, pas une donnée de compte).
const LS_CURRENCY = "preferred_currency";
const SUPPORTED_CURRENCIES = ["USD", "EUR", "XOF"];

export function getCurrency() {
  const stored = localStorage.getItem(LS_CURRENCY);
  return SUPPORTED_CURRENCIES.includes(stored) ? stored : "USD";
}

export function setCurrency(currency) {
  if (SUPPORTED_CURRENCIES.includes(currency)) localStorage.setItem(LS_CURRENCY, currency);
}

// Taux fixes vers XOF (repris tels quels de l'ancien FIXED_RATES_TO_XOF de
// dashboard.js, lui-même aligné sur USD_RATE dans backend/routes/payout.py)
// - pas un taux de marché en direct. EUR/XOF = parité officielle UEMOA/CEMAC.
const FIXED_RATES_TO_XOF = { XOF: 1, USD: 577.325, EUR: 655.957 };

export function getRate(from, to) {
  if (from === to) return 1;
  const fromToXof = FIXED_RATES_TO_XOF[from];
  const toToXof = FIXED_RATES_TO_XOF[to];
  if (!fromToXof || !toToXof) return 1;
  return fromToXof / toToXof;
}

export function formatMoney(value, currency) {
  return Number(value || 0).toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " " + currency;
}
