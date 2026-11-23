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

const BUILDNESS_US_STATE_NAMES = new Map(BUILDNESS_US_STATES);

export function buildnessStatusLabel(status) {
  if (status === "draft") return "Dossier enregistré";
  if (status === "submitted") return "Envoyé à doola";
  if (status === "processing") return "LLC en cours de formation";
  if (status === "completed") return "LLC formée";
  if (status === "failed") return "Échec";
  return status;
}

// Formateur dédié (pas formatSessionTime de parametres.js) : les deux
// vues ne doivent dépendre que de shared/core, jamais l'une de l'autre.
function formatBuildnessDate(value) {
  if (!value || isNaN(new Date(value))) return "—";
  return new Date(value).toLocaleDateString("fr-FR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// Tout ce qui peut intéresser le marchand une fois son dossier envoyé -
// affiché à CHAQUE étape (pas seulement "completed") : nom de la société
// et État dès que connus, EIN une fois obtenu, dernière étape réussie
// (utile si le statut final est "failed", pour savoir où ça s'est
// arrêté), et la date de dernière mise à jour.
export function buildnessDetailRowsHtml(data) {
  const rows = [];
  if (data.company_name) rows.push(["Nom de la société", data.company_name]);
  if (data.state) rows.push(["État de formation", BUILDNESS_US_STATE_NAMES.get(data.state) || data.state]);
  if (data.ein_number) rows.push(["EIN (identifiant fiscal)", data.ein_number]);
  if (data.last_successful_step) rows.push(["Dernière étape réussie", buildnessStatusLabel(data.last_successful_step)]);
  if (data.updated_at) rows.push(["Dernière mise à jour", formatBuildnessDate(data.updated_at)]);
  if (!rows.length) return "";
  return `
    <div class="params-row-list params-promo-details">
      ${rows.map(([label, value]) => `<div class="params-info-row"><span>${label}</span><strong>${value}</strong></div>`).join("")}
    </div>
  `;
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
