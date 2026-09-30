// Vue "Transactions" — port fidèle de transactions.html + transactions.js
// (la plus volumineuse des 7 vues : KPI, graphique Chart.js, activité
// paginée, wallet + historique, widgets Stripe Connect, exports CSV/PDF).
import { apiFetch } from "../core/apiClient.js";
import { setViewStyles } from "../core/styleLoader.js";
import { showToast } from "../shared/toast.js";
import { showUpgradeModal } from "../shared/modalUpgrade.js";

const STRIPE_PUBLISHABLE_KEY =
  "pk_test_51TJYk921oAuf4OUmVuqkub7cs2OUkWGpYlS4IgpfZrF7p6lY4v1YxRirVv1QSZD8Qof4JU78mmLgexh5wINo0vlo00c7HTwz5x";

const TEMPLATE = `
<div id="transactions-lock" class="lock-overlay" style="display: none;">
  <div class="lock-card">
    <div class="lock-icon"><i class="fa-solid fa-lock"></i></div>
    <h3>Historique des transactions</h3>
    <p>Débloquez l'historique complet, les statistiques avancées, l'export CSV et PDF avec le plan Pro.</p>
    <button class="btn btn-warning fw-bold" onclick="upgrade('pro')">⚡ Passer au Pro</button>
  </div>
</div>
<div id="transactions-normal-view">
  <div class="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-3">
    <div>
      <h4 class="page-title text-muted"><i class="fa-solid fa-credit-card"></i> Transactions</h4>
      <div class="page-subtitle">Historique de tous vos paiements</div>
    </div>
    <div id="export-actions" class="d-flex gap-2">
      <button id="exportFinancialReportBtn" class="btn btn-export"><i class="bi bi-bank me-1"></i>Rapport financier Stripe</button>
      <button id="showStripeActivityBtn" class="btn btn-export"><i class="bi bi-stripe me-1"></i>Activité Stripe Connect</button>
      <button id="exportBtn" class="btn btn-export"><i class="bi bi-download me-1"></i>Exporter CSV</button>
      <button id="exportPdfBtn" class="btn btn-export"><i class="bi bi-file-earmark-pdf me-1"></i>Exporter PDF</button>
    </div>
  </div>
  <div class="dashboard-layout">
    <div class="main-dashboard-content">
      <div id="kpi-row" class="row g-3 mb-4">
        <div class="col-md-4">
          <div class="wallet-hover-wrapper position-relative">
            <div class="card-epay">
              <div class="d-flex justify-content-between align-items-start">
                <div><div class="kpi-label"> total Solde </div><h4 id="wallet-balance" class="kpi-value green text-dark text-muted">0 XOF</h4></div>
                <button id="retraitBtn" class="btn btn-sm px-3 py-2 retrait-btn" data-bs-toggle="modal" data-bs-target="#withdrawModal">Retirer</button>
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
        <div class="col-md-4"><div class="card-epay"><div class="kpi-label">Montant verrouillé</div><h4 id="locked-amount" class="kpi-value yellow text-dark text-muted">0 XOF</h4><div id="locked-countdown" class="kpi-sub">Chargement...</div></div></div>
        <div class="col-md-4"><div class="card-epay"><div class="kpi-label">Total reçu</div><h4 id="total-xof" class="kpi-value cyan text-dark text-muted">0 XOF</h4><div class="kpi-sub">Revenus cumulés</div></div></div>
        <div class="col-md-4"><div class="card-epay"><div class="kpi-label"> Montant en attente</div><h4 id="pending-xof" class="kpi-value yellow text-dark text-muted">0 XOF</h4><div class="kpi-sub">Paiements en attente</div></div></div>
        <div class="col-md-4">
          <div class="card-epay">
            <div class="kpi-label">paiements réussis ce mois</div>
            <h4 class="kpi-value purple text-dark text-muted"><span id="links-created">0</span></h4>
            <div class="kpi-sub"><span id="links-paid" style="color:#4ade80; font-weight:700;">0</span></div>
            <div class="mini-progress"><div id="links-progress-bar" class="mini-progress-bar" style="width: 0%;"></div></div>
          </div>
        </div>
        <div class="col-md-4">
          <div class="card-epay position-relative" id="successCard">
            <div class="kpi-label">Taux de réussite</div>
            <h4 id="success-rate" class="kpi-value text-dark text-muted green">0%</h4>
            <div id="chartTooltip" style="display:none; position:absolute; top:10px; right:10px; width:320px; height:240px; padding:10px; z-index:1000;"><canvas id="statusChart"></canvas></div>
            <div class="kpi-sub">Transactions réussies ce mois</div>
          </div>
        </div>
      </div>
      <div class="toolbar">
        <div class="filter-row-1">
          <div class="search-wrap"><i class="bi bi-search"></i><input type="text" id="search-input" class="search-input" placeholder="Rechercher par client, email..."></div>
          <div class="date-group"><div class="date-pill"><small>Du</small><input type="date" id="startDate"></div><div class="date-pill"><small>Au</small><input type="date" id="endDate"></div></div>
          <button id="rafraichirBtn" class="btn btn-refresh"><i class="bi bi-arrow-clockwise"></i></button>
        </div>
        <button class="chip active" data-statut="">Tous</button>
        <button class="chip" data-statut="paid">Réussi</button>
        <button class="chip" data-statut="pending">En attente</button>
        <button class="chip" data-statut="expired">Échoué</button>
        <div class="date-group ms-2">
          <button class="chip type-chip active" data-type="">Toute activité</button>
          <button class="chip type-chip" data-type="payment">Paiements</button>
          <button class="chip type-chip" data-type="withdraw">Retraits</button>
          <button class="chip type-chip" data-type="transfer">Transferts</button>
        </div>
        <select id="filter-statut">
          <option value="">Tous les statuts</option>
          <option value="paid">Réussi</option>
          <option value="pending">En attente</option>
          <option value="expired">Échoué</option>
        </select>
      </div>
      <div id="detail-view" class="table-wrap mt-3 text-muted" style="display:none;">
        <button id="fermerDetailBtn" class="btn btn-sm mb-3" style="background:#f9fafb; border:1px solid #e5e7eb; color:#6b7280;"><i class="bi bi-arrow-left"></i> Retour</button>
        <h4 id="detail-title" class="fw-bold mb-1 text-muted"></h4>
        <div id="detail-sub" class="text-muted mb-4" style="font-size:0.85rem;"></div>
        <div id="detail-body" class="text-muted"></div>
      </div>
      <div class="table-wrap mt-3">
        <div class="d-flex justify-content-between align-items-center mb-3">
          <span class="table-title">Toutes les transactions</span>
          <span id="nb-transactions" class="count-badge">0 transactions</span>
        </div>
        <div id="transactions-scroll-box" style="max-height: 500px; overflow-y: auto;">
          <table class="table table-hover align-middle">
            <thead><tr><th>Client</th><th>Montant</th><th>Status</th><th>Date</th><th></th></tr></thead>
            <tbody id="tbody-transactions"></tbody>
          </table>
        </div>
        <div id="loading-more" class="text-center py-3 d-none"><span class="text-muted">Chargement...</span></div>
        <div id="etat-vide" class="text-center py-5">
          <p style="font-size: 2rem;"><i class="fa-solid fa-credit-card"></i></p>
          <p class="text-muted">Aucune transaction pour le moment</p>
          <small class="text-muted">Partagez votre lien de paiement pour commencer à recevoir</small>
        </div>
      </div>
    </div>
  </div>
</div>
<div id="stripe-connect-view" style="display: none;">
  <div class="d-flex justify-content-between align-items-center flex-wrap gap-3 mb-4">
    <div><h4 class="page-title text-muted"><i class="bi bi-stripe"></i> Activité Stripe Connect</h4><div class="page-subtitle">Consultez vos paiements et versements Stripe</div></div>
    <button id="backToTransactionsBtn" class="btn btn-export"><i class="bi bi-arrow-left me-1"></i>Retour aux transactions</button>
  </div>
  <div class="card-epay p-4 mb-4"><h5 class="fw-bold mb-3">Paiements Stripe</h5><div id="connect-payments"></div></div>
  <div class="card-epay p-4 mb-4"><h5 class="fw-bold mb-3">Virements Stripe</h5><div id="connect-payouts"></div></div>
</div>
<div class="modal fade" id="stripeReportModal" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-lg modal-dialog-centered modal-dialog-scrollable">
    <div class="modal-content" style="background: #ffffff; color: #111827; border-radius: 16px; border: 1px solid #e5e7eb;">
      <div class="modal-header border-0 pb-0"><h5 class="modal-title fw-bold" style="font-size: 1.25rem;">Rapport de solde Stripe</h5><button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Fermer"></button></div>
      <div class="modal-body px-4 py-3"><div id="stripe-balance-report" style="width: 100%;"></div></div>
    </div>
  </div>
</div>
<div class="modal fade" id="detailModal" tabindex="-1">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content"><div class="modal-header border-0"><h5 class="modal-title fw-bold">Détails</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body px-4" id="detailModalBody"></div></div>
  </div>
</div>
`;

// #withdrawModal est rendu à part, injecté dans document.body (pas dans le
// TEMPLATE ci-dessus) : #main-content a position:relative + z-index:1
// (sidebar.css), ce qui crée un contexte d'empilement qui enfermait le
// z-index:1055 du modal en dessous du .modal-backdrop que Bootstrap ajoute
// directement dans body (z-index:1050) — rendant le modal visible mais non
// cliquable. En sortant le modal de #main-content, il rejoint le même
// contexte d'empilement que son propre backdrop, où son z-index reprend
// effet normalement.
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

  let transactions = [];
  let offset = 0;
  const limit = 10;
  let isLoading = false;
  let currentType = "";
  let statusChart = null;
  let lockedCountdownIntervals = [];
  const boundListeners = [];
  function on(target, type, fn) {
    if (!target) return;
    target.addEventListener(type, fn);
    boundListeners.push({ target, type, fn });
  }

  const statusMap = { paid: "Réussi", pending: "En attente", expired: "Échoué" };
  const avatarPalette = ["#22d3ee", "#facc15", "#ec4899", "#4ade80", "#a78bfa", "#fb923c", "#60a5fa", "#f87171"];
  function avatarColor(str) {
    let h = 0;
    for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) % avatarPalette.length;
    return avatarPalette[h];
  }
  const typeIcon = { payment: "bi-credit-card", withdraw: "bi-bank", transfer: "bi-arrow-left-right" };
  function statusBadgeClass(status) {
    if (["paid", "success"].includes(status)) return "badge-success";
    if (["pending", "processing"].includes(status)) return "badge-warning";
    return "badge-danger";
  }

  function renderStatusChart(paid, pending, failed) {
    const ctx = document.getElementById("statusChart");
    if (!ctx) return;
    if (statusChart) statusChart.destroy();
    const centerTextPlugin = {
      id: "centerText",
      beforeDraw(chart) {
        const { ctx } = chart;
        const meta = chart.getDatasetMeta(0);
        if (!meta.data.length) return;
        const x = meta.data[0].x;
        const y = meta.data[0].y;
        const total = paid + pending + failed;
        const percent = total > 0 ? ((paid / total) * 100).toFixed(1) : 0;
        ctx.save();
        ctx.font = "bold 26px Arial";
        ctx.fillStyle = "#ffffff";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(percent + "%", x, y);
        ctx.restore();
      },
    };
    statusChart = new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: ["Payés", "En attente", "Échoués"],
        datasets: [{ data: [paid, pending, failed], backgroundColor: ["#4ade80", "#facc15", "#f87171"], borderWidth: 0 }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "55%",
        plugins: { legend: { position: "right", align: "center", labels: { color: "white", boxWidth: 18, boxHeight: 18, padding: 20, usePointStyle: false } } },
      },
      plugins: [centerTextPlugin],
    });
  }

  function afficherTransactions(data) {
    const tbody = document.getElementById("tbody-transactions");
    const vide = document.getElementById("etat-vide");
    if (data.length === 0) {
      if (offset === 0) {
        tbody.innerHTML = "";
        vide.classList.remove("d-none");
        document.getElementById("nb-transactions").textContent = "0 transactions";
      }
      return;
    }
    vide.classList.add("d-none");
    document.getElementById("nb-transactions").textContent = `${transactions.length} transaction${transactions.length > 1 ? "s" : ""}`;
    const html = data
      .map((t, i) => {
        const amount = t.amount_local ?? t.amount;
        const currency = t.currency_local ?? t.currency;
        const displayName = t.type === "payment" ? t.label || "Client" : t.label || "Transfert";
        const color = avatarColor(displayName || "x");
        return `
        <tr onclick="voirDetailActivite(${i})" style="cursor:pointer;">
          <td>
            <div class="d-flex align-items-center gap-3">
              <div class="avatar" style="background:${color};">${t.type === "payment" ? (displayName ? displayName[0].toUpperCase() : "?") : `<i class="bi ${typeIcon[t.type] || "bi-arrow-left-right"}"></i>`}</div>
              <div><div class="fw-semibold">${displayName}</div><small style="color: #9ca3af; font-size:0.75rem;">${t.type === "payment" ? "Client" : t.type === "withdraw" ? "Retrait" : "Transfert"}</small></div>
            </div>
          </td>
          <td><span class="amount-cell">${amount.toLocaleString("fr-FR")}</span><span class="amount-currency">${currency}</span></td>
          <td><span class="status-pill ${statusBadgeClass(t.status)}">${statusMap[t.status] || t.status}</span></td>
          <td style="color: #6b7280; font-size: 0.85rem;">${t.date && !isNaN(new Date(t.date)) ? new Date(t.date).toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "N/A"}</td>
          <td style="text-align:right;"><button onclick="event.stopPropagation()" style="background:#f9fafb; border:1px solid #e5e7eb; color:#6b7280; width:32px; height:32px; border-radius:8px; cursor:pointer;"><i class="bi bi-eye"></i></button></td>
        </tr>
      `;
      })
      .join("");
    tbody.innerHTML = offset === 0 ? html : tbody.innerHTML + html;
  }

  function voirDetailActivite(index) {
    const t = transactions[index];
    if (!t) return;
    const d = t.details || {};
    let rows = [];
    const displayName = t.type === "payment" ? t.label : t.label || "Transfert";
    const amount = t.amount_local ?? t.amount;
    const currency = t.currency_local ?? t.currency;
    if (t.type === "payment") {
      rows = [
        ["Montant reçu", `${amount.toLocaleString("fr-FR")} ${currency}`],
        ["Montant d'origine", `${d.amount_origin ?? "-"} ${d.currency_origin ?? ""}`],
        ["Taux utilisé", d.rate_used ?? "-"],
        ["Frais", `${d.fee_amount ?? 0}`],
        ["Carte", `${d.card_brand ?? "-"} •••• ${d.card_last4 ?? "----"}`],
        ["Expiration carte", d.card_exp_month && d.card_exp_year ? `${d.card_exp_month}/${d.card_exp_year}` : "-"],
        ["Session Stripe", d.stripe_session_id ?? "-"],
        ["Payment Intent", d.stripe_payment_intent_id ?? "-"],
        ["Compte Stripe", d.stripe_account_id ?? "-"],
        ["Lien de paiement", d.link_id ?? "-"],
      ];
    } else if (t.type === "withdraw") {
      rows = [
        ["Montant", `${amount.toLocaleString("fr-FR")} ${currency}`],
        ["Référence", d.reference ?? "-"],
        ["Payout Stripe", d.stripe_payout_id ?? "-"],
        ["Traité le", d.processed_at ? new Date(d.processed_at).toLocaleString("fr-FR") : "-"],
      ];
    } else if (t.type === "transfer") {
      rows = [
        ["Montant", `${amount.toLocaleString("fr-FR")} ${currency}`],
        ["Référence", d.reference ?? "-"],
        ["Correspondant", d.counterparty_email ?? "-"],
        ["Frais", `${d.fee_amount ?? 0} XOF`],
        ["Note", d.description ?? "-"],
      ];
    }
    document.getElementById("detail-title").innerText = displayName;
    document.getElementById("detail-sub").innerText =
      (t.type === "payment" ? "Paiement" : t.type === "withdraw" ? "Retrait" : "Transfert") + " · " + (statusMap[t.status] || t.status);
    document.getElementById("detail-body").innerHTML = rows
      .map(([label, value]) => `<div class="d-flex justify-content-between py-3 border-bottom"><span class="text-muted">${label}</span><span class="fw-semibold" style="text-align:right; max-width:60%; word-break:break-all;">${value}</span></div>`)
      .join("");
    document.getElementById("kpi-row").style.display = "none";
    container.querySelector(".toolbar").style.display = "none";
    container.querySelector(".table-wrap:not(#detail-view)").style.display = "none";
    document.getElementById("detail-view").style.display = "block";
  }

  function fermerDetail() {
    document.getElementById("kpi-row").style.display = "";
    container.querySelector(".toolbar").style.display = "";
    container.querySelector(".table-wrap:not(#detail-view)").style.display = "";
    document.getElementById("detail-view").style.display = "none";
  }

  async function chargerTransactions() {
    if (isLoading) return;
    isLoading = true;
    const loader = document.getElementById("loading-more");
    loader.classList.remove("d-none");
    try {
      const statut = document.getElementById("filter-statut").value;
      const params = new URLSearchParams({ offset, limit });
      if (currentType) params.append("type", currentType);
      if (statut) params.append("status", statut);
      const res = await apiFetch(`/activity?${params}`);
      const data = await res.json();
      transactions = [...transactions, ...data];
      afficherTransactions(data);
      offset += data.length;
    } catch (err) {
      console.error("Erreur activity:", err);
    }
    isLoading = false;
    loader.classList.add("d-none");
  }

  async function rafraichir(btn) {
    try {
      btn.style.transition = "transform 0.6s linear";
      btn.style.transform = "rotate(360deg)";
      btn.disabled = true;
      await chargerTransactions();
      await loadStats();
    } catch (err) {
      console.error(err);
    } finally {
      setTimeout(() => {
        btn.style.transform = "rotate(0deg)";
        btn.disabled = false;
      }, 600);
    }
  }

  function filtrerTransactions() {
    const search = document.getElementById("search-input").value.toLowerCase();
    const statut = document.getElementById("filter-statut").value;
    const filtered = transactions.filter((t) => {
      const matchSearch = (t.label || "").toLowerCase().includes(search);
      const matchStatus = !statut || t.status === statut;
      return matchSearch && matchStatus;
    });
    afficherTransactions(filtered);
  }

  function setStatutChip(el) {
    container.querySelectorAll(".chip:not(.type-chip)").forEach((c) => c.classList.remove("active"));
    el.classList.add("active");
    const select = document.getElementById("filter-statut");
    select.value = el.dataset.statut;
    select.dispatchEvent(new Event("change"));
  }

  function setTypeChip(el) {
    container.querySelectorAll(".type-chip").forEach((c) => c.classList.remove("active"));
    el.classList.add("active");
    currentType = el.dataset.type;
    offset = 0;
    transactions = [];
    chargerTransactions();
  }

  function renderStats(stats) {
    document.getElementById("total-xof").innerText = (stats.total_received || 0).toLocaleString("fr-FR") + " XOF";
    document.getElementById("pending-xof").innerText = (stats.pending_total || 0).toLocaleString("fr-FR") + " XOF";
    document.getElementById("success-rate").innerText = (stats.success_rate || 0) + "%";
    renderStatusChart(stats.paid_links || 0, stats.pending_links || 0, stats.failed_links || 0);
  }

  function renderLinksKPI(plan) {
    const usage = plan.usage || {};
    const createdEl = document.getElementById("links-created");
    const paidEl = document.getElementById("links-paid");
    const barEl = document.getElementById("links-progress-bar");
    const linksLimitText = usage.links_limit === null ? "Illimité" : usage.links_limit;
    const paidLimitText = usage.paid_limit === null ? "Illimité" : usage.paid_limit;
    if (createdEl) createdEl.innerText = `${usage.paid_count ?? 0} / ${paidLimitText}`;
    if (paidEl) paidEl.innerText = `Sur un maximum de ${linksLimitText} liens créés`;
    if (barEl) {
      const pct = usage.paid_limit > 0 ? Math.min(100, (usage.paid_count / usage.paid_limit) * 100) : 0;
      barEl.style.width = pct + "%";
    }
  }

  async function loadStats() {
    try {
      const response = await apiFetch("/stats");
      const stats = await response.json();
      window.LAST_STATS = stats;
      renderStatusChart(stats.paid_count || 0, stats.pending_link || 0, stats.failed_links || 0);
      document.getElementById("success-rate").textContent = (stats.success_rate || 0) + "%";
      renderStats(stats);
    } catch (error) {
      console.error("Erreur stats:", error);
    }
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

  async function loadPlan() {
    try {
      const res = await apiFetch("/me/plan");
      const data = await res.json();
      window.GLOBAL_PLAN = data;
      const paidLimit = data.usage ? data.usage.paid_limit : data.paid_limit;
      renderLinksKPI(data);
      return paidLimit;
    } catch (err) {
      console.error("Erreur loadPlan:", err);
    }
  }

  async function downloadFinancialReport() {
    const startDate = document.getElementById("startDate").value;
    const endDate = document.getElementById("endDate").value;
    if (!startDate || !endDate) {
      showToast("Sélectionne une période (du / au) avant de générer le rapport", "warning");
      return;
    }
    const btn = document.getElementById("exportFinancialReportBtn");
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<i class="bi bi-hourglass-split me-1"></i> Génération en cours...`;
    try {
      const res = await apiFetch(`/reports/financial?start_date=${startDate}&end_date=${endDate}`);
      if (res.status === 403) {
        showUpgradeModal();
        return;
      }
      if (!res.ok) {
        let message = "Erreur lors de la génération du rapport";
        try {
          const data = await res.json();
          if (typeof data.detail === "string") message = data.detail;
        } catch (e) {}
        showToast(message, "error");
        return;
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `rapport_financier_${startDate}_${endDate}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      showToast("Rapport téléchargé avec succès");
    } catch (err) {
      showToast("Erreur de connexion au serveur", "error");
    } finally {
      btn.disabled = false;
      btn.innerHTML = originalText;
    }
  }

  async function initStripeBalanceReport() {
    const mountEl = document.getElementById("stripe-balance-report");
    if (!mountEl) return;
    const modalEl = document.getElementById("stripeReportModal");
    if (modalEl) new bootstrap.Modal(modalEl).show();
    if (mountEl.hasChildNodes()) return;
    try {
      const stripeConnectInstance = window.StripeConnect.init({
        publishableKey: STRIPE_PUBLISHABLE_KEY,
        fetchClientSecret: async () => {
          const res = await apiFetch("/reports/connect-session", { method: "POST" });
          if (!res.ok) throw new Error("Impossible de créer la session Stripe");
          const data = await res.json();
          return data.client_secret;
        },
        appearance: { overlays: "dialog", variables: { colorPrimary: "#facc15" } },
      });
      const balanceReport = stripeConnectInstance.create("balance-report");
      mountEl.innerHTML = "";
      mountEl.appendChild(balanceReport);
    } catch (err) {
      console.error("Erreur chargement rapport Stripe:", err);
      showToast("Impossible de charger le rapport Stripe", "error");
    }
  }

  async function exportCSV() {
    const startDate = document.getElementById("startDate").value;
    const endDate = document.getElementById("endDate").value;
    const status = document.getElementById("filter-statut")?.value;
    const params = new URLSearchParams();
    if (status) params.append("status", status);
    if (startDate) params.append("start_date", startDate);
    if (endDate) params.append("end_date", endDate);
    const res = await apiFetch(`/export/csv?${params}`);
    if (res.status === 403) {
      showUpgradeModal();
      return;
    }
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "transactions.csv";
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  async function exportPDF() {
    const startDate = document.getElementById("startDate").value;
    const endDate = document.getElementById("endDate").value;
    const status = document.getElementById("filter-statut").value;
    const params = new URLSearchParams();
    if (status) params.append("status", status);
    if (startDate) params.append("start_date", startDate);
    if (endDate) params.append("end_date", endDate);
    const res = await apiFetch(`/export/pdf?${params}`);
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "rapport_xepay.pdf";
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  async function loadConnectWidgets(accountId) {
    try {
      const response = await apiFetch(`/stripe/connect/${accountId}/account-session`, { method: "POST" });
      if (!response.ok) throw new Error(await response.text());
      const data = await response.json();
      const connectInstance = window.StripeConnect.init({ publishableKey: STRIPE_PUBLISHABLE_KEY, fetchClientSecret: async () => data.client_secret });
      document.getElementById("connect-payments").replaceChildren(connectInstance.create("payments"));
      document.getElementById("connect-payouts").replaceChildren(connectInstance.create("payouts"));
    } catch (error) {
      console.error("Erreur widgets Connect :", error);
    }
  }

  // --- Câblage des événements (remplace les onclick= inline + addEventListener top-level) ---
  container.querySelectorAll(".chip[data-statut]").forEach((chip) => on(chip, "click", () => setStatutChip(chip)));
  container.querySelectorAll(".type-chip").forEach((chip) => on(chip, "click", () => setTypeChip(chip)));
  on(document.getElementById("search-input"), "input", filtrerTransactions);
  on(document.getElementById("rafraichirBtn"), "click", function () {
    rafraichir(this);
  });
  on(document.getElementById("fermerDetailBtn"), "click", fermerDetail);
  on(document.getElementById("filter-statut"), "change", () => {
    offset = 0;
    transactions = [];
    chargerTransactions();
  });
  on(document.getElementById("exportFinancialReportBtn"), "click", initStripeBalanceReport);
  on(document.getElementById("exportBtn"), "click", exportCSV);
  on(document.getElementById("exportPdfBtn"), "click", exportPDF);

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
      await Promise.all([chargerWallet(), loadWalletHistory(), chargerTransactions()]);
    } catch (err) {
      showToast("Erreur serveur, veuillez réessayer", "error");
      closeWithdrawModalCleanly();
    } finally {
      confirmBtn.disabled = false;
    }
  });

  const successCard = document.getElementById("successCard");
  const chartTooltip = document.getElementById("chartTooltip");
  if (successCard && chartTooltip) {
    on(successCard, "mouseenter", () => (chartTooltip.style.display = "block"));
    on(successCard, "mouseleave", () => (chartTooltip.style.display = "none"));
  }

  const scrollBox = document.getElementById("transactions-scroll-box");
  const onScroll = () => {
    if (scrollBox.scrollTop + scrollBox.clientHeight >= scrollBox.scrollHeight - 50) chargerTransactions();
  };
  on(scrollBox, "scroll", onScroll);

  const modalUpgradeEl = document.getElementById("modalUpgrade");
  const onShownUpgrade = () => {
    document.querySelectorAll("#modalUpgrade .reveal").forEach((el, index) => setTimeout(() => el.classList.add("visible"), index * 100));
  };
  on(modalUpgradeEl, "shown.bs.modal", onShownUpgrade);

  let widgetsLoaded = false;
  const showStripeBtn = document.getElementById("showStripeActivityBtn");
  const backBtn = document.getElementById("backToTransactionsBtn");
  const normalView = document.getElementById("transactions-normal-view");
  const stripeView = document.getElementById("stripe-connect-view");
  on(showStripeBtn, "click", async () => {
    normalView.style.display = "none";
    stripeView.style.display = "block";
    if (widgetsLoaded) return;
    showStripeBtn.disabled = true;
    try {
      const res = await apiFetch("/stripe/status");
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      const accountId = data.profile?.stripe_account_id;
      if (!accountId) throw new Error("stripe_account_id introuvable");
      await loadConnectWidgets(accountId);
      widgetsLoaded = true;
    } catch (error) {
      console.error("Erreur chargement Stripe Connect :", error);
      showToast("Impossible de charger l'activité Stripe Connect", "error");
    } finally {
      showStripeBtn.disabled = false;
    }
  });
  on(backBtn, "click", () => {
    stripeView.style.display = "none";
    normalView.style.display = "block";
  });

  const retraitBtn = document.getElementById("retraitBtn");
  const exportActionsEl = document.getElementById("export-actions");
  const mq = window.matchMedia("(max-width: 768px)");
  let placeButton = () => {};
  if (retraitBtn && exportActionsEl) {
    const originalParent = retraitBtn.parentElement;
    const originalNextSibling = retraitBtn.nextSibling;
    placeButton = (query) => {
      if (query.matches) exportActionsEl.prepend(retraitBtn);
      else if (originalNextSibling) originalParent.insertBefore(retraitBtn, originalNextSibling);
      else originalParent.appendChild(retraitBtn);
    };
    placeButton(mq);
    mq.addEventListener("change", placeButton);
  }

  // window.upgrade est exposé globalement par app.js (modale partagée persistante)
  window.voirDetailActivite = voirDetailActivite;
  window.annulerRetrait = annulerRetrait;

  (async () => {
    const res = await apiFetch("/me");
    const user = await res.json();
    const lock = document.getElementById("transactions-lock");
    if (user.plan === "free") {
      document.body.classList.add("locked-page");
      lock.style.display = "flex";
      return;
    }
    document.body.classList.remove("locked-page");
    lock.style.display = "none";
    loadStats();
    chargerTransactions();
    chargerWallet();
    loadWalletHistory();
    loadPlan();
  })();

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
      if (statusChart) statusChart.destroy();
      lockedCountdownIntervals.forEach(clearInterval);
      boundListeners.forEach(({ target, type, fn }) => target.removeEventListener(type, fn));
      mq.removeEventListener("change", placeButton);
      document.body.classList.remove("locked-page");
      delete window.voirDetailActivite;
      delete window.annulerRetrait;
    },
  };
}
