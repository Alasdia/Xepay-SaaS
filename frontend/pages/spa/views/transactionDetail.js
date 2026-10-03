// Vues "Détail d'une transaction" (paiement ou retrait) — routes à part
// entière (/dash/workspace/{id}/transactions/paiements/py/{id} et
// .../transactions/retraits/wd/{id}), chargées depuis les endpoints détail
// dédiés (GET /payments/{id}, GET /withdrawals/{id}) plutôt que depuis la
// liste /activity déjà en mémoire dans transactions.js. Réutilise le même
// gabarit visuel (mêmes classes, mêmes lignes) que l'ancien panneau de
// détail inline de transactions.js pour ne pas changer le design existant.
import { apiFetch } from "../core/apiClient.js";
import { setViewStyles } from "../core/styleLoader.js";
import { navigate } from "../core/router.js";
import { getWorkspaceId } from "../core/state.js";
import { showUpgradeModal } from "../shared/modalUpgrade.js";

const statusMap = { paid: "Réussi", pending: "En attente", expired: "Échoué" };

const TEMPLATE = `
<div class="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-3">
  <div>
    <h4 class="page-title text-muted"><i class="fa-solid fa-credit-card"></i> Détail</h4>
    <div class="page-subtitle">Détail de la transaction</div>
  </div>
</div>
<div class="table-wrap mt-3 text-muted">
  <button id="backBtn" class="btn btn-sm mb-3" style="background:#f9fafb; border:1px solid #e5e7eb; color:#6b7280;"><i class="bi bi-arrow-left"></i> Retour</button>
  <div id="detail-content">
    <h4 id="detail-title" class="fw-bold mb-1 text-muted"></h4>
    <div id="detail-sub" class="text-muted mb-4" style="font-size:0.85rem;"></div>
    <div id="detail-body" class="text-muted"></div>
  </div>
  <div id="detail-error" class="text-center py-5 d-none">
    <p style="font-size: 2rem;"><i class="fa-solid fa-triangle-exclamation"></i></p>
    <p class="text-muted" id="detail-error-message"></p>
  </div>
</div>
`;

function backToTransactionsUrl() {
  const workspaceId = getWorkspaceId() || "me";
  return `/dash/workspace/${encodeURIComponent(workspaceId)}/transactions`;
}

function renderRows(rows) {
  return rows
    .map(
      ([label, value]) =>
        `<div class="d-flex justify-content-between py-3 border-bottom"><span class="text-muted">${label}</span><span class="fw-semibold" style="text-align:right; max-width:60%; word-break:break-all;">${value}</span></div>`
    )
    .join("");
}

function renderPayment(item) {
  const d = item.details || {};
  const amount = Number(item.amount || 0);
  return {
    title: item.label || "Client",
    sub: "Paiement · " + (statusMap[item.status] || item.status),
    rows: [
      ["Montant reçu", `${amount.toLocaleString("fr-FR")} ${item.currency}`],
      ["Montant d'origine", `${d.amount_origin ?? "-"} ${d.currency_origin ?? ""}`],
      ["Taux utilisé", d.rate_used ?? "-"],
      ["Frais", `${d.fee_amount ?? 0}`],
      ["Carte", `${d.card_brand ?? "-"} •••• ${d.card_last4 ?? "----"}`],
      ["Expiration carte", d.card_exp_month && d.card_exp_year ? `${d.card_exp_month}/${d.card_exp_year}` : "-"],
      ["Session Stripe", d.stripe_session_id ?? "-"],
      ["Payment Intent", d.stripe_payment_intent_id ?? "-"],
      ["Compte Stripe", d.stripe_account_id ?? "-"],
      ["Lien de paiement", d.link_id ?? "-"],
    ],
  };
}

function renderWithdrawal(item) {
  const d = item.details || {};
  const amount = Number(item.amount || 0);
  return {
    title: item.label || "Retrait",
    sub: "Retrait · " + (statusMap[item.status] || item.status),
    rows: [
      ["Montant", `${amount.toLocaleString("fr-FR")} ${item.currency}`],
      ["Référence", d.reference ?? "-"],
      ["Payout Stripe", d.stripe_payout_id ?? "-"],
      ["Traité le", d.processed_at ? new Date(d.processed_at).toLocaleString("fr-FR") : "-"],
    ],
  };
}

async function mountDetail(container, { endpoint, render }) {
  await setViewStyles(["transactions.css"]);
  container.innerHTML = TEMPLATE;

  const backBtn = document.getElementById("backBtn");
  const onBack = () => navigate(backToTransactionsUrl());
  backBtn.addEventListener("click", onBack);

  const contentEl = document.getElementById("detail-content");
  const errorEl = document.getElementById("detail-error");
  const errorMessageEl = document.getElementById("detail-error-message");

  function showError(message) {
    contentEl.style.display = "none";
    errorEl.classList.remove("d-none");
    errorMessageEl.textContent = message;
  }

  try {
    const res = await apiFetch(endpoint);
    if (!res.ok) {
      let message = "Introuvable ou accès refusé";
      try {
        const data = await res.json();
        if (typeof data.detail === "string") message = data.detail;
      } catch (e) {}
      if (res.status === 403 && message.toLowerCase().includes("plan")) {
        showUpgradeModal();
      }
      showError(message);
    } else {
      const item = await res.json();
      const { title, sub, rows } = render(item);
      document.getElementById("detail-title").innerText = title;
      document.getElementById("detail-sub").innerText = sub;
      document.getElementById("detail-body").innerHTML = renderRows(rows);
    }
  } catch (err) {
    console.error("Erreur chargement détail transaction :", err);
    showError("Erreur de connexion au serveur");
  }

  return {
    unmount() {
      backBtn.removeEventListener("click", onBack);
    },
  };
}

export function mountPayment(container, params) {
  return mountDetail(container, {
    endpoint: `/payments/${encodeURIComponent(params.paymentId)}`,
    render: renderPayment,
  });
}

export function mountWithdrawal(container, params) {
  return mountDetail(container, {
    endpoint: `/withdrawals/${encodeURIComponent(params.withdrawalId)}`,
    render: renderWithdrawal,
  });
}
