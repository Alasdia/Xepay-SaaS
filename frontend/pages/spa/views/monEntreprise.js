// Vue "Mon entreprise" — suivi dédié du dossier Buildness (LLC US + EIN
// via doola) après son lancement, demandé le 2026-11-23 : Paramètres >
// Entreprise reste le point d'entrée pour LANCER/RELANCER un dossier
// (formulaire complet, voir spa/views/parametres.js), cette vue-ci n'est
// que pour CONSULTER l'avancement - accessible directement depuis la
// sidebar (juste sous Commerce), sans repasser par Paramètres.
//
// Affichage et logique de polling partagés avec la carte Paramètres >
// Entreprise via shared/buildnessStatus.js, pour ne jamais dupliquer ce
// formatage entre les deux vues.
import { setViewStyles } from "../core/styleLoader.js";
import { navigate } from "../core/router.js";
import { getWorkspaceId } from "../core/state.js";
import {
  BUILDNESS_TERMINAL_STATUSES,
  BUILDNESS_POLL_INTERVAL_MS,
  buildnessStatusLabel,
  buildnessDetailRowsHtml,
  fetchBuildnessStatus,
} from "../shared/buildnessStatus.js";

const TEMPLATE = `
  <h1 class="page-title"><i class="fa-solid fa-building"></i> Mon entreprise</h1>
  <p class="params-subsection-sub" style="max-width:640px; margin-bottom:24px;">Suivi de la formation de votre société américaine (LLC) et de l'obtention de son EIN (identifiant fiscal fédéral) via notre partenaire doola.</p>
  <div id="mon-entreprise-container"><p class="text-muted">Chargement...</p></div>
`;

function notStartedHtml() {
  return `
    <div class="params-promo-card">
      <h3 class="params-promo-title">Aucun dossier en cours</h3>
      <p class="params-promo-sub">Vous n'avez pas encore lancé la création de votre société américaine.</p>
      <div class="params-promo-actions">
        <button type="button" id="p-mon-entreprise-goto-params" class="create-client-btn">Créer ma société</button>
      </div>
    </div>
  `;
}

function statusCardHtml(data) {
  const status = data.status;
  const statusClass = status === "completed" ? "params-promo-status-done" : status === "failed" ? "params-promo-status-failed" : "";
  const icon = status === "completed" ? "✅" : status === "failed" ? "⚠️" : "⏳";
  return `
    <div class="params-promo-card">
      <div class="params-promo-status ${statusClass}">${icon} ${buildnessStatusLabel(status)}${status !== "completed" && status !== "failed" ? "..." : ""}</div>
      ${buildnessDetailRowsHtml(data)}
      <div class="params-promo-actions mt-3">
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
      // Debug demandé le 2026-11-24 : réponse de GET /buildness/status
      // (déjà mise en forme par le backend Xepay à partir de ce que
      // doola a renvoyé - la vraie réponse brute de l'API doola ne
      // quitte jamais le serveur, rien de plus précis n'est consultable
      // depuis le navigateur).
      console.log("[Mon entreprise] GET /buildness/status ->", data);
      render(data);
      if (data.status && !BUILDNESS_TERMINAL_STATUSES.has(data.status)) {
        stopPolling();
        pollTimer = setInterval(async () => {
          try {
            const next = await fetchBuildnessStatus();
            console.log("[Mon entreprise] GET /buildness/status (polling) ->", next);
            render(next);
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
