// Partagé entre Paramètres > Entreprise (carte de lancement/relance,
// voir spa/views/parametres.js) et la vue "Mon entreprise" (spa/views/
// monEntreprise.js, suivi dédié après lancement du dossier) - les deux
// affichent exactement les mêmes informations issues de GET /buildness/
// status, extrait ici le 2026-11-23 pour ne jamais dupliquer ce
// formatage entre les deux vues (même principe que shared/toast.js).

import { apiFetch } from "../core/apiClient.js";
import { getWorkspaceId } from "../core/state.js";

export const BUILDNESS_TERMINAL_STATUSES = new Set(["completed", "failed"]);
export const BUILDNESS_POLL_INTERVAL_MS = 5000;

export const BUILDNESS_US_STATES = [
  ["AL", "Alabama"], ["AK", "Alaska"], ["AZ", "Arizona"], ["AR", "Arkansas"],
  ["CA", "Californie"], ["CO", "Colorado"], ["CT", "Connecticut"], ["DE", "Delaware"],
  ["FL", "Floride"], ["GA", "Géorgie"], ["HI", "Hawaï"], ["ID", "Idaho"],
  ["IL", "Illinois"], ["IN", "Indiana"], ["IA", "Iowa"], ["KS", "Kansas"],
  ["KY", "Kentucky"], ["LA", "Louisiane"], ["ME", "Maine"], ["MD", "Maryland"],
  ["MA", "Massachusetts"], ["MI", "Michigan"], ["MN", "Minnesota"], ["MS", "Mississippi"],
  ["MO", "Missouri"], ["MT", "Montana"], ["NE", "Nebraska"], ["NV", "Nevada"],
  ["NH", "New Hampshire"], ["NJ", "New Jersey"], ["NM", "Nouveau-Mexique"], ["NY", "New York"],
  ["NC", "Caroline du Nord"], ["ND", "Dakota du Nord"], ["OH", "Ohio"], ["OK", "Oklahoma"],
  ["OR", "Oregon"], ["PA", "Pennsylvanie"], ["RI", "Rhode Island"], ["SC", "Caroline du Sud"],
  ["SD", "Dakota du Sud"], ["TN", "Tennessee"], ["TX", "Texas"], ["UT", "Utah"],
  ["VT", "Vermont"], ["VA", "Virginie"], ["WA", "Washington"], ["WV", "Virginie-Occidentale"],
  ["WI", "Wisconsin"], ["WY", "Wyoming"], ["DC", "District de Columbia"],
];

export function buildnessStatusLabel(status) {
  if (status === "draft") return "Dossier enregistré";
  if (status === "submitted") return "Envoyé à doola";
  if (status === "processing") return "LLC en cours de formation";
  if (status === "completed") return "LLC formée";
  if (status === "failed") return "Échec";
  return status;
}

export async function fetchBuildnessStatus() {
  const merchantId = getWorkspaceId();
  const res = await apiFetch(`/buildness/status/${encodeURIComponent(merchantId)}`);
  if (res.status === 403) {
    const err = new Error("forbidden");
    err.isForbidden = true;
    throw err;
  }
  if (!res.ok) throw new Error("Impossible de récupérer le statut Buildness");
  return res.json();
}

// Réponse BRUTE de doola (GET /v1/partner/companies/{id}), sans aucune
// mise en forme côté Xepay - demandé le 2026-11-24 pour inspection/
// conception UI (voir spa/views/monEntreprise.js, console.log). Jamais
// utilisée pour l'affichage réel - fetchBuildnessStatus (ci-dessus)
// reste la seule source pour le rendu du marchand.
export async function fetchBuildnessRawStatus() {
  const merchantId = getWorkspaceId();
  const res = await apiFetch(`/buildness/status/${encodeURIComponent(merchantId)}/raw`);
  if (!res.ok) throw new Error("Impossible de récupérer le statut brut doola");
  return res.json();
}
