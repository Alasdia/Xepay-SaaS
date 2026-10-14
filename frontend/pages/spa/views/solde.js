// Vue "Solde" — KPI finance (Solde disponible, Montant verrouillé) et
// retrait de fonds, déplacés depuis la vue Paiements (views/transactions.js)
// où ils cohabitaient avec les KPI d'activité. Reprend telle quelle la
// logique wallet/retrait qui y existait (chargerWallet, loadWalletHistory,
// annulerRetrait, #withdrawModal) ; transactions.css est réutilisé tel quel
// (.card-epay / .kpi-value / .wallet-popup / .retrait-btn) pour ne pas
// dupliquer ce CSS dans un nouveau fichier.
import { apiFetch } from "../core/apiClient.js";
import { setViewStyles } from "../core/styleLoader.js";
import { showToast } from "../shared/toast.js";

const TEMPLATE = `
<div class="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-3">
  <div>
    <h4 class="page-title text-muted"><i class="fa-solid fa-wallet"></i> Solde</h4>
    <div class="page-subtitle">Votre solde disponible et vos fonds verrouillés</div>
  </div>
</div>
<div class="dashboard-layout subview-mode">
  <div class="main-dashboard-content">
    <div id="kpi-row" class="row g-3 mb-4">
      <div class="col-md-6">
        <div class="wallet-hover-wrapper position-relative">
          <div class="card-epay">
            <div class="d-flex justify-content-between align-items-start">
              <div><div class="kpi-label">Solde disponible</div><h4 id="wallet-balance" class="kpi-value green text-dark text-muted">0 XOF</h4></div>
              <button id="retraitBtn" class="btn retrait-btn" data-bs-toggle="modal" data-bs-target="#withdrawModal">Retirer des fonds</button>
            </div>
            <div class="kpi-sub">Disponible maintenant</div>
          </div>
          <div id="walletHistoryPopup" class="wallet-popup">
            <h6 class="mb-3">Historique du wallet</h6>
            <div id="wallet-scroll-box" style="max-height: 500px; overflow-y: auto;"><div id="walletHistoryList"></div></div>
            <div id="wallet-loading-more" class="text-center py-3 d-none"><span class="text-muted">Chargement...</span></div>
          </div>
        </div>
      </div>
      <div class="col-md-6">
        <div class="card-epay">
          <div class="kpi-label">Montant verrouillé</div>
          <h4 id="locked-amount" class="kpi-value yellow text-dark text-muted">0 XOF</h4>
          <div id="locked-countdown" class="kpi-sub">Chargement...</div>
        </div>
      </div>
    </div>
  </div>
</div>
`;

// #withdrawModal est rendu à part, injecté dans document.body : #main-content
// a position:relative + z-index:1 (sidebar.css), ce qui enfermait le
// z-index:1055 du modal en dessous du .modal-backdrop que Bootstrap ajoute
// directement dans body (z-index:1050) — rendant le modal visible mais non
// cliquable. En sortant le modal de #main-content, il rejoint le même
// contexte d'empilement que son propre backdrop, où son z-index reprend
// effet normalement (même principe que #stripeReportModal dans
// views/transactions.js).
const WITHDRAW_MODAL_HTML = `
<div class="modal fade" id="withdrawModal" tabindex="-1">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content">
      <div class="modal-header border-0"><h5 class="modal-title fw-bold">Retirer de l'argent</h5><button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button></div>
      <div class="modal-body px-4"><div class="mb-3"><label class="form-label">Montant</label><input type="number" id="withdrawAmount" class="form-control" placeholder="Ex: 5000"></div></div>
      <div class="modal-footer border-0"><button class="btn btn-secondary" data-bs-dismiss="modal">Annuler</button><button id="confirmWithdrawBtn" class="btn btn-cyan">Confirmer</button></div>
    </div>
  </div>
</div>
`;

export async function mount(container) {
  await setViewStyles(["transactions.css"]);
  container.innerHTML = TEMPLATE;
  document.body.insertAdjacentHTML("beforeend", WITHDRAW_MODAL_HTML);

  let lockedCountdownIntervals = [];
  const boundListeners = [];
  function on(target, type, fn) {
    if (!target) return;
    target.addEventListener(type, fn);
    boundListeners.push({ target, type, fn });
  }

  function formatCountdown(targetDate) {
    const now = new Date();
    const diff = new Date(targetDate) - now;
    if (diff <= 0) return "Disponible maintenant";
    const totalSeconds = Math.floor(diff / 1000);
    const days = Math.floor(totalSeconds / 86400);
    const hours = Math.floor((totalSeconds % 86400) / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    let result = "Disponible dans ";
    if (days > 0) result += `${days}j `;
    if (hours > 0 || days > 0) result += `${hours}h `;
    if (minutes > 0 || hours > 0 || days > 0) result += `${minutes}min `;
    result += `${seconds}s`;
    return result;
  }

  async function chargerWallet() {
    try {
      const res = await apiFetch("/wallet/me");
      const data = await res.json();
      document.getElementById("wallet-balance").innerText =
        Number(data.available || 0).toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " XOF";
      const lockedAmountEl = document.getElementById("locked-amount");
      if (lockedAmountEl) {
        lockedAmountEl.innerText =
          Number(data.locked_amount || 0).toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " XOF";
      }
      const lockedCountdownEl = document.getElementById("locked-countdown");
      if (lockedCountdownEl) {
        if (data.next_available_at) {
          const lockedTarget = new Date(data.next_available_at);
          const update = () => (lockedCountdownEl.innerText = formatCountdown(lockedTarget));
          update();
          lockedCountdownIntervals.push(setInterval(update, 1000));
        } else {
          lockedCountdownEl.innerText = "Aucun montant verrouillé";
        }
      }
    } catch (err) {
      console.error("Erreur wallet:", err);
    }
  }

  async function loadWalletHistory() {
    const historyList = document.getElementById("walletHistoryList");
    try {
      const res = await apiFetch("/wallet/history");
      const data = await res.json();
      if (!data.transactions || data.transactions.length === 0) {
        historyList.innerHTML = "<small>Aucun mouvement wallet</small>";
        return;
      }
      historyList.innerHTML = data.transactions
        .map((tx) => {
          const estRetraitEnAttente = tx.type === "withdraw" && tx.status === "pending";
          const boutonAnnuler =
            estRetraitEnAttente && tx.withdrawal_id
              ? `<div style="margin-top: 8px; text-align: right;"><button onclick="annulerRetrait('${tx.withdrawal_id}')" style="background:#facc15;color:#111827;border:none;padding:5px 12px;border-radius:6px;font-size:11px;font-weight:600;cursor:pointer;">Annuler le retrait</button></div>`
              : "";
          return `
          <div class="wallet-item" style="border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 10px; margin-bottom: 10px;">
            <div class="wallet-row"><span class="wallet-label">Type :</span><span class="wallet-value">${tx.type === "deposit" ? "Dépôt" : tx.type === "withdraw" ? "Retrait" : tx.type}</span></div>
            <div class="wallet-row"><span class="wallet-label">Montant :</span><span class="wallet-value ${tx.direction === "in" ? "text-success" : "text-danger"}">${tx.direction === "in" ? "+" : "-"}${Number(tx.amount).toLocaleString("fr-FR")} XOF</span></div>
            <div class="wallet-row"><span class="wallet-label">Date :</span><span class="wallet-value">${new Date(tx.created_at).toLocaleString("fr-FR")}</span></div>
            <div class="wallet-row"><span class="wallet-label">Référence :</span><span class="wallet-value">${tx.reference || "N/A"}</span></div>
            <div class="wallet-row"><span class="wallet-label">Note :</span><span class="wallet-value">${tx.description || "-"}</span></div>
            ${boutonAnnuler}
          </div>
        `;
        })
        .join("");
    } catch (e) {
      if (historyList) historyList.innerHTML = "<small>Erreur chargement historique</small>";
    }
  }

  async function annulerRetrait(retraitId) {
    if (!retraitId) {
      showToast("Identifiant du retrait introuvable", "error");
      return;
    }
    if (!confirm("Voulez-vous vraiment annuler ce retrait ? Les fonds seront recrédités.")) return;
    try {
      const res = await apiFetch(`/withdrawals/${retraitId}/cancel`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) {
        showToast(data.detail || "Erreur lors de l'annulation", "error");
        return;
      }
      showToast("Retrait annulé avec succès !", "success");
      await loadWalletHistory();
      await chargerWallet();
    } catch (err) {
      console.error("Erreur annulation retrait :", err);
      showToast("Erreur de connexion au serveur", "error");
    }
  }

  function closeWithdrawModalCleanly() {
    const modalEl = document.getElementById("withdrawModal");
    const modal = bootstrap.Modal.getInstance(modalEl);
    if (modal) modal.hide();
    setTimeout(() => {
      document.body.classList.remove("modal-open");
      document.body.style.removeProperty("overflow");
      document.body.style.removeProperty("padding-right");
      document.querySelectorAll(".modal-backdrop").forEach((el) => el.remove());
    }, 300);
  }

  const confirmBtn = document.getElementById("confirmWithdrawBtn");
  on(confirmBtn, "click", async () => {
    if (confirmBtn.disabled) return;
    confirmBtn.disabled = true;
    const amount = parseFloat(document.getElementById("withdrawAmount").value);
    if (!amount || amount <= 0) {
      alert("Montant invalide");
      confirmBtn.disabled = false;
      return;
    }
    try {
      const res = await apiFetch("/withdraw", { method: "POST", body: { amount } });
      const data = await res.json();
      if (!res.ok) {
        let message = "Impossible d'effectuer ce retrait";
        if (data.detail === "Permission insuffisante") message = "Seul le propriétaire du compte peut effectuer un retrait";
        else if (typeof data.detail === "string") message = data.detail;
        showToast(message, "error");
        closeWithdrawModalCleanly();
        return;
      }
      const res2 = await apiFetch(`/withdraw/${data.id}/process`, { method: "POST" });
      const data2 = await res2.json();
      if (!res2.ok) {
        showToast(data2.detail || "Erreur lors du traitement Stripe", "error");
        closeWithdrawModalCleanly();
        return;
      }
      showToast("Retrait envoyé avec succès");
      closeWithdrawModalCleanly();
      document.getElementById("withdrawAmount").value = "";
      await Promise.all([chargerWallet(), loadWalletHistory()]);
    } catch (err) {
      showToast("Erreur serveur, veuillez réessayer", "error");
      closeWithdrawModalCleanly();
    } finally {
      confirmBtn.disabled = false;
    }
  });

  window.annulerRetrait = annulerRetrait;

  chargerWallet();
  loadWalletHistory();

  return {
    unmount() {
      const withdrawModalEl = document.getElementById("withdrawModal");
      const withdrawModalInstance = withdrawModalEl && bootstrap.Modal.getInstance(withdrawModalEl);
      if (withdrawModalInstance) {
        withdrawModalInstance.hide();
        withdrawModalInstance.dispose();
        document.body.classList.remove("modal-open");
        document.body.style.removeProperty("overflow");
        document.body.style.removeProperty("padding-right");
        document.querySelectorAll(".modal-backdrop").forEach((el) => el.remove());
      }
      withdrawModalEl?.remove();
      lockedCountdownIntervals.forEach(clearInterval);
      boundListeners.forEach(({ target, type, fn }) => target.removeEventListener(type, fn));
      delete window.annulerRetrait;
    },
  };
}
