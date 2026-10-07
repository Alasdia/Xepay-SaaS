// Vue "Détail d'un lien" — route à part entière
// (/dash/workspace/{id}/liens/lk/{id}), chargée depuis l'endpoint détail
// dédié (GET /links/{id}). Réutilise les mêmes classes CSS que la carte de
// liens.js (.lien-card, .lien-header, .lien-status, .lien-url...) pour
// garder le même design que la liste.
import { apiFetch } from "../core/apiClient.js";
import { setViewStyles } from "../core/styleLoader.js";
import { navigate } from "../core/router.js";
import { getWorkspaceId } from "../core/state.js";

const STATUS_LABEL = { paid: "Payé", expired: "Expiré", pending: "En attente" };

function statusClass(status) {
  if (status === "paid") return "status-paid";
  if (status === "expired") return "status-expired";
  if (status === "pending") return "status-pending";
  return "status-active";
}

const TEMPLATE = `
<div class="mb-4">
  <h4 class="fw-bold mb-1">🔗 Détail du lien</h4>
  <small class="text-muted">Informations complètes sur ce lien de paiement</small>
</div>
<button id="backBtn" class="btn btn-sm mb-3" style="background:#f9fafb; border:1px solid #e5e7eb; color:#6b7280;"><i class="bi bi-arrow-left"></i> Retour</button>
<div id="lien-detail-content">
  <div class="lien-card" style="cursor: default;">
    <div class="lien-content">
      <div class="lien-header">
        <div class="lien-infos">
          <h6 id="lien-detail-name"></h6>
          <small id="lien-detail-expiration" style="font-weight:500;"></small>
          <div class="montant" id="lien-detail-amount"></div>
        </div>
        <div class="lien-status" id="lien-detail-status"></div>
      </div>
    </div>
    <div class="lien-url" id="lien-detail-url"></div>
  </div>
</div>
<div id="lien-detail-error" class="text-center py-5 d-none">
  <p class="text-muted"></p>
</div>
`;

function backToLiensUrl() {
  const workspaceId = getWorkspaceId() || "me";
  return `/dash/workspace/${encodeURIComponent(workspaceId)}/liens`;
}

function renderLien(lien) {
  const amount =
    typeof lien.amount === "number" ? `${new Intl.NumberFormat("fr-FR").format(lien.amount)} ${lien.currency}` : "Montant invalide";
  document.getElementById("lien-detail-name").textContent = lien.name;
  document.getElementById("lien-detail-amount").textContent = amount;
  document.getElementById("lien-detail-url").textContent = lien.url;
  document.getElementById("lien-detail-url").className = `lien-url ${statusClass(lien.status)}`;

  const statusEl = document.getElementById("lien-detail-status");
  statusEl.textContent = STATUS_LABEL[lien.status] || "Actif";
  statusEl.className = `lien-status ${statusClass(lien.status)}`;

  const expirationEl = document.getElementById("lien-detail-expiration");
  if (lien.status === "expired") {
    expirationEl.textContent = "Expiré";
    expirationEl.style.color = "red";
  } else {
    const exp = new Date(lien.expires_at);
    expirationEl.textContent = `Expire le ${exp.toLocaleDateString("fr-FR")} à ${exp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
    expirationEl.style.color = "orange";
  }
}

export async function mount(container, params) {
  await setViewStyles(["responsive.css", "liens.css"]);
  container.innerHTML = TEMPLATE;

  const backBtn = document.getElementById("backBtn");
  const onBack = () => navigate(backToLiensUrl());
  backBtn.addEventListener("click", onBack);

  const contentEl = document.getElementById("lien-detail-content");
  const errorEl = document.getElementById("lien-detail-error");

  function showError(message) {
    contentEl.style.display = "none";
    errorEl.classList.remove("d-none");
    errorEl.querySelector("p").textContent = message;
  }

  try {
    const res = await apiFetch(`/links/${encodeURIComponent(params.linkId)}`);
    if (!res.ok) {
      let message = "Lien introuvable ou accès refusé";
      try {
        const data = await res.json();
        if (typeof data.detail === "string") message = data.detail;
      } catch (e) {}
      showError(message);
    } else {
      const lien = await res.json();
      renderLien(lien);
    }
  } catch (err) {
    console.error("Erreur chargement détail lien :", err);
    showError("Erreur de connexion au serveur");
  }

  return {
    unmount() {
      backBtn.removeEventListener("click", onBack);
    },
  };
}
