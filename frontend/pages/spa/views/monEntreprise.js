// Vue "Mon entreprise" — suivi dédié du dossier Buildness (LLC US + EIN
// via doola) après son lancement, demandé le 2026-11-23 : Paramètres >
// Entreprise reste le point d'entrée pour LANCER/RELANCER un dossier
// (formulaire complet, voir spa/views/parametres.js), cette vue-ci n'est
// que pour CONSULTER l'avancement - accessible directement depuis la
// sidebar (juste sous Commerce), sans repasser par Paramètres.
//
// Affichage refait le 2026-11-24 (demande explicite - "plus
// professionnel", fini la carte teintée .params-promo-card utilisée
// pour la CTA de lancement) : carte blanche dédiée (.mon-entreprise-*,
// parametres.css), repère de progression à 4 segments, grille de
// statistiques plutôt qu'une simple liste de lignes.
import { setViewStyles } from "../core/styleLoader.js";
import { navigate } from "../core/router.js";
import { getWorkspaceId } from "../core/state.js";
import {
  BUILDNESS_TERMINAL_STATUSES,
  BUILDNESS_POLL_INTERVAL_MS,
  BUILDNESS_US_STATES,
  buildnessStatusLabel,
  fetchBuildnessStatus,
  fetchBuildnessRawStatus,
} from "../shared/buildnessStatus.js";

const BUILDNESS_US_STATE_NAMES = new Map(BUILDNESS_US_STATES);
const BUILDNESS_STEPS = ["draft", "submitted", "processing", "completed"];

const TEMPLATE = `
  <h1 class="page-title"><i class="fa-solid fa-building"></i> Mon entreprise</h1>
  <p class="params-subsection-sub" style="max-width:640px; margin-bottom:24px;">Suivi de la formation de votre société américaine (LLC) et de l'obtention de son EIN (identifiant fiscal fédéral) via notre partenaire doola.</p>
  <div id="mon-entreprise-container"><p class="text-muted">Chargement...</p></div>
`;

function notStartedHtml() {
  return `
    <div class="mon-entreprise-card">
      <div class="mon-entreprise-header">
        <div class="mon-entreprise-icon"><i class="fa-solid fa-building-circle-xmark"></i></div>
        <div>
          <h3 class="mon-entreprise-title">Aucun dossier en cours</h3>
          <p class="mon-entreprise-status">Vous n'avez pas encore lancé la création de votre société américaine.</p>
        </div>
      </div>
      <div class="params-promo-actions">
        <button type="button" id="p-mon-entreprise-goto-params" class="create-client-btn">Créer ma société</button>
      </div>
    </div>
  `;
}

// 4 segments (draft/submitted/processing/completed) - colorés jusqu'à
// la dernière étape réussie (voire tous en rouge si failed), jamais un
// stepper interactif, juste un repère visuel de progression.
function stepsHtml(data) {
  const upTo = BUILDNESS_STEPS.indexOf(data.last_successful_step || data.status);
  return `
    <div class="mon-entreprise-steps">
      ${BUILDNESS_STEPS.map((_, i) => {
        const cls = data.status === "failed" && i > upTo ? "" : (i <= upTo ? (data.status === "failed" ? "failed" : "done") : "");
        return `<div class="mon-entreprise-step ${cls}"></div>`;
      }).join("")}
    </div>
  `;
}

function statHtml(label, value) {
  return `
    <div class="mon-entreprise-stat">
      <div class="mon-entreprise-stat-label">${label}</div>
      <div class="mon-entreprise-stat-value">${value}</div>
    </div>
  `;
}

function statusCardHtml(data) {
  const status = data.status;
  const statusClass = status === "completed" ? "status-done" : status === "failed" ? "status-failed" : "status-processing";
  const icon = status === "completed" ? "fa-circle-check" : status === "failed" ? "fa-circle-exclamation" : "fa-clock";
  const stats = [];
  if (data.state) stats.push(statHtml("État de formation", BUILDNESS_US_STATE_NAMES.get(data.state) || data.state));
  stats.push(statHtml("EIN (identifiant fiscal)", data.ein_number || "Pas encore émis"));
  if (data.last_successful_step) stats.push(statHtml("Dernière étape réussie", buildnessStatusLabel(data.last_successful_step)));
  if (data.updated_at) stats.push(statHtml("Dernière mise à jour", new Date(data.updated_at).toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" })));

  return `
    <div class="mon-entreprise-card">
      <div class="mon-entreprise-header">
        <div class="mon-entreprise-icon"><i class="fa-solid fa-building"></i></div>
        <div>
          <h3 class="mon-entreprise-title">${data.company_name || "Votre société"}</h3>
          <p class="mon-entreprise-status ${statusClass}"><i class="fa-solid ${icon}"></i> ${buildnessStatusLabel(status)}${status !== "completed" && status !== "failed" ? "..." : ""}</p>
        </div>
      </div>
      ${stepsHtml(data)}
      <div class="mon-entreprise-grid">${stats.join("")}</div>
      <div class="params-promo-actions">
        <button type="button" id="p-mon-entreprise-goto-params" class="create-client-btn">${status === "failed" ? "Réessayer" : "Créer une autre société"}</button>
      </div>
    </div>
  `;
}

export async function mount(container) {
  await setViewStyles(["parametres.css"]);
  container.innerHTML = TEMPLATE;

  let pollTimer = null;
  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  function gotoParametresEntreprise() {
    navigate(`/dash/workspace/${encodeURIComponent(getWorkspaceId())}/parametres/entreprise`);
  }

  function render(data) {
    const el = document.getElementById("mon-entreprise-container");
    if (!el) return;
    el.innerHTML = (!data.status || data.status === "not_started") ? notStartedHtml() : statusCardHtml(data);
    const btn = document.getElementById("p-mon-entreprise-goto-params");
    if (btn) btn.addEventListener("click", gotoParametresEntreprise);
  }

  async function load() {
    try {
      const data = await fetchBuildnessStatus();
      render(data);
      // Debug demandé le 2026-11-24 : réponse BRUTE de doola (GET /v1/
      // partner/companies/{id}, voir GET /buildness/status/{id}/raw côté
      // backend) - jamais utilisée pour l'affichage, uniquement pour
      // inspecter en console ce que doola renvoie réellement.
      fetchBuildnessRawStatus()
        .then((raw) => console.log("[Mon entreprise] Réponse BRUTE doola ->", raw))
        .catch((err) => console.warn("[Mon entreprise] Echec recuperation reponse brute doola :", err));
      if (data.status && !BUILDNESS_TERMINAL_STATUSES.has(data.status)) {
        stopPolling();
        pollTimer = setInterval(async () => {
          try {
            const next = await fetchBuildnessStatus();
            render(next);
            fetchBuildnessRawStatus()
              .then((raw) => console.log("[Mon entreprise] Réponse BRUTE doola (polling) ->", raw))
              .catch(() => {});
            if (BUILDNESS_TERMINAL_STATUSES.has(next.status)) stopPolling();
          } catch (err) {
            if (err.isForbidden) stopPolling();
          }
        }, BUILDNESS_POLL_INTERVAL_MS);
      }
    } catch (err) {
      const el = document.getElementById("mon-entreprise-container");
      if (el) {
        el.innerHTML = err.isForbidden
          ? `<p class="text-muted">Vous n'avez pas les droits pour consulter cette page.</p>`
          : `<p class="text-muted">Erreur de chargement.</p>`;
      }
    }
  }

  load();

  return {
    unmount() {
      stopPolling();
    },
  };
}
