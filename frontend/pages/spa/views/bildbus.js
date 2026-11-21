// Vue BildBus — formation de LLC US + EIN via doola (voir backend/
// routes/bildbus.py, backend/routes/webhook/doola.py). Un seul fichier,
// pas de sous-vues (contrairement à commerce.js) : c'est un flux
// linéaire à une seule étape visible côté marchand - formulaire, puis
// suivi jusqu'à "completed"/"failed" - jamais plusieurs sections
// indépendantes à naviguer entre elles.
import { apiFetch } from "../core/apiClient.js";
import { getWorkspaceId } from "../core/state.js";
import { setViewStyles } from "../core/styleLoader.js";
import { showToast } from "../shared/toast.js";

// Code ISO 3166-2:US à 2 lettres, requis par doola (voir
// BildBusOnboardRequest.state, backend/models.py) - liste complète : un
// marchand peut légitimement vouloir former sa LLC dans n'importe quel
// État, pas seulement les plus courants (Delaware/Wyoming).
const US_STATES = [
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

// Étapes fixes du stepper - "failed" n'est PAS une 5e étape, c'est l'étape
// courante au moment de l'échec qui bascule en rouge (voir statusTemplate).
const STEPS = [
  { key: "draft", label: "Dossier enregistré" },
  { key: "submitted", label: "Envoyé à doola" },
  { key: "processing", label: "LLC en cours de formation" },
  { key: "completed", label: "LLC formée - EIN obtenu" },
];
const STEP_INDEX = Object.fromEntries(STEPS.map((s, i) => [s.key, i]));

const TERMINAL_STATUSES = new Set(["completed", "failed"]);
const POLL_INTERVAL_MS = 5000;

function escapeHTML(value) {
  const div = document.createElement("div");
  div.textContent = value ?? "";
  return div.innerHTML;
}

function formTemplate() {
  const options = US_STATES.map(
    ([code, name]) => `<option value="${code}">${name} (${code})</option>`
  ).join("");
  return `
    <div class="bildbus-header">
      <h4>🏛️ BildBus - Créer ma LLC américaine</h4>
      <small class="text-muted">Formez votre société aux États-Unis et obtenez votre EIN, nécessaire pour activer Stripe Connect.</small>
    </div>
    <div class="card-epay p-4 bildbus-form-card">
      <form id="bildbus-onboard-form">
        <div class="form-group">
          <label for="bb-company-name">Nom de la LLC</label>
          <input type="text" id="bb-company-name" placeholder="Ex: Xepay Ventures LLC" required>
        </div>
        <div class="form-group">
          <label for="bb-state">État de formation souhaité</label>
          <select id="bb-state" required>
            <option value="" disabled selected>Choisir un État</option>
            ${options}
          </select>
        </div>
        <div class="form-group">
          <label for="bb-first-name">Prénom du fondateur</label>
          <input type="text" id="bb-first-name" required>
        </div>
        <div class="form-group">
          <label for="bb-last-name">Nom du fondateur</label>
          <input type="text" id="bb-last-name" required>
        </div>
        <div class="form-group">
          <label for="bb-email">Email du fondateur</label>
          <input type="email" id="bb-email" required>
        </div>
        <button type="submit" id="bildbus-submit-btn" class="bildbus-submit-btn">
          Lancer la création de ma LLC
        </button>
      </form>
    </div>
  `;
}

function statusTemplate(data) {
  const status = data.status;
  // data.last_successful_step (voir backend/models.py) : dernière étape
  // qui a RÉELLEMENT réussi - jamais mis à jour sur un échec. Quand
  // status="failed", l'étape qui a échoué est celle JUSTE APRÈS, pas
  // systématiquement la dernière du stepper.
  const lastDoneIndex = STEP_INDEX[data.last_successful_step] ?? -1;
  const currentIndex = status === "failed"
    ? Math.min(lastDoneIndex + 1, STEPS.length - 1)
    : (STEP_INDEX[status] ?? -1);

  const stepsHtml = STEPS.map((step, i) => {
    let cls = "bildbus-step";
    let icon = `${i + 1}`;
    if (status === "failed" && i === currentIndex) {
      cls += " bildbus-step-failed";
      icon = "✕";
    } else if (i < currentIndex || status === "completed" && i <= currentIndex) {
      cls += " bildbus-step-done";
      icon = "✓";
    } else if (i === currentIndex) {
      cls += " bildbus-step-current";
    }
    return `
      <div class="${cls}">
        <span class="bildbus-step-dot">${icon}</span>
        <span class="bildbus-step-label">${escapeHTML(step.label)}</span>
      </div>
    `;
  }).join("");

  const isPolling = !TERMINAL_STATUSES.has(status);

  const einBox = status === "completed" && data.ein_number ? `
    <div class="bildbus-ein-box">
      <div class="bildbus-ein-label">EIN de ${escapeHTML(data.company_name || "votre LLC")}</div>
      <div class="bildbus-ein-value">${escapeHTML(data.ein_number)}</div>
    </div>
  ` : "";

  const failedBox = status === "failed" ? `
    <div class="bildbus-failed-box">
      La demande a échoué. Vous pouvez réessayer avec de nouvelles informations.
      <div class="mt-2">
        <button type="button" id="bildbus-retry-btn" class="bildbus-submit-btn">Réessayer</button>
      </div>
    </div>
  ` : "";

  return `
    <div class="bildbus-header">
      <h4>🏛️ BildBus - ${escapeHTML(data.company_name || "Ma LLC")}</h4>
      <small class="text-muted">
        ${isPolling ? '<span class="bildbus-spinner"></span>Suivi en temps réel de la formation de votre LLC.' : "Suivi terminé."}
      </small>
    </div>
    <div class="card-epay p-4 bildbus-form-card">
      <div class="bildbus-stepper">${stepsHtml}</div>
      ${einBox}
      ${failedBox}
    </div>
  `;
}

export async function mount(container, params = {}) {
  await setViewStyles(["commerce.css", "liens.css", "bildbus.css"]);

  let pollTimer = null;

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  async function fetchStatus() {
    const merchantId = getWorkspaceId();
    const res = await apiFetch(`/bildbus/status/${encodeURIComponent(merchantId)}`);
    if (res.status === 403) {
      const err = new Error("forbidden");
      err.isForbidden = true;
      throw err;
    }
    if (!res.ok) throw new Error("Impossible de récupérer le statut BildBus");
    return res.json();
  }

  function renderForbidden() {
    stopPolling();
    container.innerHTML = `
      <div class="bildbus-header">
        <h4>🏛️ BildBus</h4>
      </div>
      <div class="card-epay p-4 bildbus-form-card bildbus-failed-box">
        Vous n'avez pas les droits pour gérer la création d'entreprise.
        Seul le propriétaire du workspace peut démarrer ou suivre ce dossier.
      </div>
    `;
  }

  function renderStatus(data) {
    container.innerHTML = statusTemplate(data);
    const retryBtn = document.getElementById("bildbus-retry-btn");
    if (retryBtn) retryBtn.addEventListener("click", renderForm);
  }

  function startPolling() {
    stopPolling();
    pollTimer = setInterval(async () => {
      try {
        const data = await fetchStatus();
        renderStatus(data);
        if (TERMINAL_STATUSES.has(data.status)) stopPolling();
      } catch (err) {
        if (err.isForbidden) {
          // Permission retirée en cours de session (ex: rôle changé) -
          // jamais juste "retenter au prochain tick" ici, contrairement à
          // une erreur réseau transitoire.
          renderForbidden();
          return;
        }
        // Erreur réseau transitoire : retentée au prochain tick, pas de
        // toast à chaque échec pour ne pas spammer l'utilisateur toutes
        // les 5 secondes si sa connexion est instable.
      }
    }, POLL_INTERVAL_MS);
  }

  async function onSubmit(e) {
    e.preventDefault();
    const btn = document.getElementById("bildbus-submit-btn");
    const originalLabel = btn.textContent;
    btn.disabled = true;
    btn.textContent = "Envoi en cours...";

    const body = {
      email: document.getElementById("bb-email").value.trim(),
      first_name: document.getElementById("bb-first-name").value.trim(),
      last_name: document.getElementById("bb-last-name").value.trim(),
      company_name: document.getElementById("bb-company-name").value.trim(),
      state: document.getElementById("bb-state").value,
    };

    try {
      const res = await apiFetch("/bildbus/onboard", { method: "POST", body });
      if (res.status === 403) {
        renderForbidden();
        return;
      }
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Échec de la demande");
      showToast("Demande envoyée - suivi en cours", "success");
      renderStatus({
        status: data.status || "draft",
        last_successful_step: data.status || "draft",
        company_name: body.company_name,
      });
      startPolling();
    } catch (err) {
      showToast(err.message || "Erreur lors de l'envoi", "error");
      btn.disabled = false;
      btn.textContent = originalLabel;
    }
  }

  function renderForm() {
    stopPolling();
    container.innerHTML = formTemplate();
    document.getElementById("bildbus-onboard-form").addEventListener("submit", onSubmit);
  }

  try {
    const data = await fetchStatus();
    if (!data.status || data.status === "not_started") {
      renderForm();
    } else {
      renderStatus(data);
      if (!TERMINAL_STATUSES.has(data.status)) startPolling();
    }
  } catch (err) {
    if (err.isForbidden) {
      renderForbidden();
    } else {
      showToast("Impossible de charger le statut BildBus", "error");
      renderForm();
    }
  }

  return {
    unmount() {
      stopPolling();
    },
  };
}
