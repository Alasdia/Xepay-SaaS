// Vue "Transactions" — port fidèle de transactions.html + transactions.js
// (la plus volumineuse des 7 vues : KPI, graphique Chart.js, activité
// paginée, wallet + historique, widgets Stripe Connect, exports CSV/PDF).
import { apiFetch } from "../core/apiClient.js";
import { setViewStyles } from "../core/styleLoader.js";
import { showToast } from "../shared/toast.js";
import { showUpgradeModal } from "../shared/modalUpgrade.js";
import { navigate } from "../core/router.js";
import { getWorkspaceId } from "../core/state.js";
import { getCurrency, getRate, formatMoney } from "../core/currency.js";
import { renderCommerceKpis, ensureCommerceKpiStyles, renderMetadataSection } from "./commerce.js";
import { initDetailsDrawer } from "../shared/detailsDrawer.js";

const STRIPE_PUBLISHABLE_KEY =
  "pk_test_51ULZVC0I86XW25IrioDmxFoRvLJhP3QC6wJ11Qil9UmVrVtiYxxnY9gyxoM7X6VPxJaKtUGF8K1j9q1dsnUU2uhB0057G12ETb";

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
      <!-- KPI finance (Solde disponible, Montant verrouillé, Montant en
           attente) déplacés vers la vue Solde (Montant en attente
           simplement retiré) — voir views/solde.js. Il ne reste ici que les
           3 KPI propres à l'activité Paiements, restylés au même gabarit
           que les KPI cliquables des sous-vues Commerce (.commerce-kpi),
           en taille agrandie (.commerce-kpi-lg) puisqu'il s'agit ici de
           simples statistiques d'affichage, pas de filtres. -->
      <div id="kpi-row" class="commerce-kpi-filters commerce-kpi-filters-lg mb-4">
        <div class="commerce-kpi commerce-kpi-display commerce-kpi-lg commerce-kpi-paiements">
          <div class="commerce-kpi-paiements-row">
            <i class="fa-solid fa-circle-check commerce-kpi-paiements-icon text-muted"></i>
            <div class="commerce-kpi-paiements-text">
              <span class="commerce-kpi-label text-muted">Paiements réussis ce mois</span>
              <strong class="commerce-kpi-value text-muted"><span id="links-created">0</span></strong>
              <span class="commerce-kpi-sub text-muted"><span id="links-paid" style="font-weight:700;">0</span></span>
            </div>
          </div>
          <div class="mini-progress"><div id="links-progress-bar" class="mini-progress-bar" style="width: 0%;"></div></div>
        </div>
        <div class="commerce-kpi commerce-kpi-display commerce-kpi-lg commerce-kpi-paiements position-relative" id="successCard">
          <div class="commerce-kpi-paiements-row">
            <i class="fa-solid fa-gauge-high commerce-kpi-paiements-icon text-muted"></i>
            <div class="commerce-kpi-paiements-text">
              <span class="commerce-kpi-label text-muted">Taux de réussite</span>
              <strong id="success-rate" class="commerce-kpi-value text-muted">0%</strong>
              <span class="commerce-kpi-sub text-muted">Transactions réussies ce mois</span>
            </div>
          </div>
          <div id="chartTooltip" style="display:none; position:absolute; top:10px; right:10px; width:320px; height:240px; padding:10px; z-index:1000;"><canvas id="statusChart"></canvas></div>
        </div>
        <div class="commerce-kpi commerce-kpi-display commerce-kpi-lg commerce-kpi-paiements">
          <div class="commerce-kpi-paiements-row">
            <i class="fa-solid fa-sack-dollar commerce-kpi-paiements-icon text-muted"></i>
            <div class="commerce-kpi-paiements-text">
              <span class="commerce-kpi-label text-muted">Total reçu</span>
              <strong id="total-xof" class="commerce-kpi-value text-muted">0 XOF</strong>
              <span class="commerce-kpi-sub text-muted">Revenus cumulés</span>
            </div>
          </div>
        </div>
      </div>
      <!-- KPI cliquables Paiements (visibles uniquement sur l'onglet
           Paiements, voir updatePaymentsViewMode) : zone indépendante du
           tableau, même style/logique que "Moyens de paiement". -->
      <div id="payments-kpi-summary" style="display:none;"></div>
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
        <!-- "Plus de filtres" (Paiements) : même ligne que les chips de
             statut ci-dessus ; le panneau Montant/Devise/Moyen de paiement
             s'ouvre en menu déroulant positionné sous le bouton. -->
        <div id="pay-more-filters-wrap" style="position:relative; display:none;">
          <button id="payMoreFiltersBtn" class="btn btn-export"><i class="bi bi-sliders me-1"></i>Plus de filtres</button>
          <div id="payMoreFiltersRow" class="filter-dropdown" style="display:none;">
            <input type="number" id="pay-min-amount" class="filter-input" placeholder="Montant min">
            <input type="number" id="pay-max-amount" class="filter-input" placeholder="Montant max">
            <select id="pay-currency" class="filter-select">
              <option value="">Devise : toutes</option>
              <option value="USD">USD</option>
              <option value="EUR">EUR</option>
              <option value="XOF">XOF</option>
            </select>
            <input type="text" id="pay-payment-method" class="filter-input" placeholder="Moyen de paiement (visa, mastercard...)">
          </div>
        </div>
        <div id="type-chip-group" class="date-group ms-2">
          <button class="chip type-chip active" data-type="">Toute activité</button>
          <button class="chip type-chip" data-type="payment">Paiements</button>
          <button class="chip type-chip" data-type="withdraw">Retraits</button>
        </div>
        <select id="filter-statut">
          <option value="">Tous les statuts</option>
          <option value="paid">Réussi</option>
          <option value="pending">En attente</option>
          <option value="expired">Échoué</option>
        </select>
      </div>
      <div class="table-wrap mt-3">
        <div class="d-flex justify-content-between align-items-center mb-3">
          <span class="table-title">Toutes les transactions</span>
          <span id="nb-transactions" class="count-badge">0 transactions</span>
        </div>
        <div id="transactions-scroll-box">
          <table class="table table-hover align-middle">
            <thead>
              <tr id="thead-row-transactions">
                <th>Client</th>
                <th>Montant</th>
                <th>Status</th>
                <th>Date</th>
                <th></th>
              </tr>
            </thead>
            <tbody id="tbody-transactions"></tbody>
          </table>
        </div>
        <div class="d-flex justify-content-between align-items-center mt-3">
          <span id="pagination-info" class="text-muted">Page 1</span>
          <div class="d-flex gap-2">
            <button id="prev-page" class="btn btn-export" disabled>
              <i class="bi bi-chevron-left"></i>
            </button>
            <button id="next-page" class="btn btn-export">
              <i class="bi bi-chevron-right"></i>
            </button>
          </div>
        </div>
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
<div class="modal fade" id="detailModal" tabindex="-1">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content"><div class="modal-header border-0"><h5 class="modal-title fw-bold">Détails</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body px-4" id="detailModalBody"></div></div>
  </div>
</div>
<!-- Détails d'un paiement (menu Action "..." du tableau) — même gabarit que
     les tiroirs Clients/Produits (voir views/commerce.js) : classes
     .customer-modal-overlay/.customer-modal partagées (commerce.css). -->
<div class="customer-modal-overlay" id="payment-details-modal">
  <div class="customer-modal customer-details-modal">
    <div class="customer-modal-header">
      <div>
        <h3>Détails du paiement</h3>
        <p id="payment-details-subtitle"></p>
      </div>
      <button type="button" class="customer-modal-close" id="close-payment-details">×</button>
    </div>
    <div id="payment-details-content"></div>
  </div>
</div>
`;

// Menu Action "..." (Rembourser / Détails du paiement) : un seul élément
// partagé par toutes les lignes, en position fixed et attaché à <body>
// (jamais dans #transactions-scroll-box, qui a overflow:hidden/auto et
// couperait le menu sur les dernières lignes du tableau) — positionné via
// getBoundingClientRect() du bouton cliqué.
const ACTION_MENU_HTML = `
<div id="payment-action-menu" class="action-menu-dropdown">
  <button type="button" class="action-menu-item" data-action="refund">Rembourser</button>
  <button type="button" class="action-menu-item" data-action="details">Détails du paiement</button>
</div>
`;

// #stripeReportModal est rendu à part, injecté dans document.body :
// #main-content a position:relative + z-index:1 (sidebar.css), ce qui
// enfermait le z-index:1055 du modal en dessous du .modal-backdrop que
// Bootstrap ajoute directement dans body (z-index:1050) — rendant le modal
// visible mais non cliquable. En sortant le modal de #main-content, il
// rejoint le même contexte d'empilement que son propre backdrop, où son
// z-index reprend effet normalement. (Le retrait de fonds/#withdrawModal
// suit le même principe, voir views/solde.js où il a été déplacé avec le
// KPI "Solde disponible".)
const STRIPE_REPORT_MODAL_HTML = `
<div class="modal fade" id="stripeReportModal" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-lg modal-dialog-centered modal-dialog-scrollable">
    <div class="modal-content" style="background: #d1d5db; color: #111827; border-radius: 0; border: 1px solid #d1d5db; box-shadow: 0 20px 50px rgba(0,0,0,.18);">
      <div class="modal-header border-0 pb-0"><h5 class="modal-title fw-bold" style="font-size: 1.25rem;">Rapport de solde Stripe</h5><button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Fermer"></button></div>
      <div class="modal-body px-4 py-3"><div id="stripe-balance-report" style="width: 100%;"></div></div>
    </div>
  </div>
</div>
`;

export async function mount(container, params = {}) {
  // commerce.css fournit les classes .customer-modal-overlay/.customer-
  // details-grid (Clients/Produits, voir views/commerce.js) réutilisées ici
  // pour le tiroir "Détails du paiement".
  await setViewStyles(["transactions.css", "commerce.css"]);
  ensureCommerceKpiStyles();
  container.innerHTML = TEMPLATE;
  document.body.insertAdjacentHTML("beforeend", STRIPE_REPORT_MODAL_HTML);
  document.body.insertAdjacentHTML("beforeend", ACTION_MENU_HTML);

  // Rapport de solde Stripe : consultation de détails -> tiroir latéral
  // droit (voir shared/detailsDrawer.js). #withdrawModal (création d'un
  // retrait) n'est volontairement pas concerné.
  initDetailsDrawer(
    document.getElementById("stripeReportModal"),
    document.querySelector("#stripeReportModal .modal-content"),
    { width: 560, instant: true }
  );

  const paymentDetailsModal = document.getElementById("payment-details-modal");
  initDetailsDrawer(paymentDetailsModal, paymentDetailsModal.querySelector(".customer-modal"));

  // Pages dédiées (/transactions/paiements|retraits, voir
  // app.js) : type verrouillé dès le montage, pas de bascule entre
  // catégories depuis cette page — les chips Toute activité/Paiements/
  // Retraits n'ont plus de raison d'être affichées.
  const fixedType = params.fixedType || null;

  let transactions = [];
  let offset = 0;
  const limit = 10;
  let isLoading = false;
  let hasNextPage = true;
  let pageNumber = 1;
  let currentType = fixedType || "";
  // Statut sélectionné via les KPI Paiements (Tous/Réussis/Remboursés/
  // Contestés/En échec/Non capturés) — prioritaire sur le select
  // #filter-statut/les chips existants quand non vide. "" = pas de filtre
  // KPI actif (comportement existant inchangé).
  let kpiPaymentStatus = "";
  let statusChart = null;
  const boundListeners = [];
  function updatePagination() {
    const prevBtn = document.getElementById("prev-page");
    const nextBtn = document.getElementById("next-page");
    const info = document.getElementById("pagination-info");
    if (prevBtn) prevBtn.disabled = pageNumber <= 1;
    if (nextBtn) nextBtn.disabled = !hasNextPage;
    if (info) info.textContent = `Page ${pageNumber}`;
  }
  function on(target, type, fn) {
    if (!target) return;
    target.addEventListener(type, fn);
    boundListeners.push({ target, type, fn });
  }

  const statusMap = { paid: "Payé", success: "Payé", pending: "En attente", expired: "Échoué", refunded: "Remboursé", partially_refunded: "Partiellement remboursé" };
  const avatarPalette = ["#22d3ee", "#facc15", "#ec4899", "#4ade80", "#a78bfa", "#fb923c", "#60a5fa", "#f87171"];
  function avatarColor(str) {
    let h = 0;
    for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) % avatarPalette.length;
    return avatarPalette[h];
  }
  const typeIcon = { payment: "bi-credit-card", withdraw: "bi-bank" };
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

  function updateTableHead() {
    const theadRow = document.getElementById("thead-row-transactions");
    if (!theadRow) return;
    theadRow.innerHTML =
      currentType === "payment"
        ? `<th>Client</th><th>Moyen de paiement</th><th>Type</th><th>Montant brut</th><th>Commission globale</th><th>Commission Xepay</th><th>Frais Stripe</th><th>Montant net marchand</th><th>Créé le</th><th>Disponible le</th><th>Statut</th><th>Actions</th>`
        : currentType === "withdraw"
        ? `<th>Référence</th><th>Méthode</th><th>Montant</th><th>Statut</th><th>Motif</th><th>Date</th>`
        : `<th>Client</th><th>Montant</th><th>Status</th><th>Date</th>`;
  }

  // Origine du paiement (Payment.source, backend) : "link" = paiement par
  // lien, "invoice"/"subscription" = facture/abonnement Connect. Absent
  // (null) sur les paiements créés avant l'ajout de ce champ - jamais
  // deviné, affiché tel quel ("-").
  const paymentSourceLabel = {
    link: "Lien",
    invoice: "Facture",
    subscription: "Abonnement",
  };

  const paymentMethodLabel = {
    card: "Carte",
    link: "Link",
    visa: "Visa",
    mastercard: "Mastercard",
    apple_pay: "Apple Pay",
    google_pay: "Google Pay",
    klarna: "Klarna",
    bancontact: "Bancontact",
    cashapp: "Cash App",
    affirm: "Affirm",
    blik: "BLIK",
    eps: "EPS",
    ideal: "iDEAL",
    cartes_bancaires: "Cartes Bancaires",
  };

  function paymentMethodIcon(method, brand, last4) {
    const icons = {
      visa: "/assets/visa.svg",
      mastercard: "/assets/mastercard.svg",
      link: "/assets/link.svg",
      apple_pay: "/assets/apple-pay.svg",
      google_pay: "/assets/google-pay.svg",
      klarna: "/assets/klarna-logo.svg",
      bancontact: "/assets/bancontact.svg",
      cashapp: "/assets/cashapp.svg",
      affirm: "/assets/affirm.svg",
      blik: "/assets/blik-logo.svg",
      eps: "/assets/eps.svg",
      ideal: "/assets/ideal.svg",
      cartes_bancaires: "/assets/carte_bancaire.svg",
      card: "/assets/carte.svg",
    };
    // brand peut être absent (carte sans marque identifiée) : repli sur
    // l'icône générique "card" plutôt que de perdre l'icône entièrement.
    const logoKey = method === "card" ? (brand || "card") : method;
    const src = icons[logoKey];
    if (!src) {
      return `<span>${paymentMethodLabel[method] ?? method ?? "-"}</span>`;
    }
    // Apple Pay/Google Pay restent des paiements carte sous le capot
    // (backend : payment_method_type devient le wallet "apple_pay"/
    // "google_pay" quand présent) — les 4 derniers chiffres restent donc
    // pertinents à afficher, pas seulement pour method === "card".
    const last4Display =
      last4 && (method === "card" || method === "apple_pay" || method === "google_pay")
        ? ` ···· ${last4}`
        : "";
    // Visa/Mastercard : logo seul, suffisamment reconnaissable - le nom
    // n'est affiché que pour les autres moyens de paiement.
    const nameLabel =
      logoKey === "visa" || logoKey === "mastercard"
        ? ""
        : paymentMethodLabel[logoKey] ?? paymentMethodLabel[method] ?? "";
    return `
      <span style="display:flex;align-items:center;gap:8px;">
        <img src="${src}" alt="${logoKey}" style="width:42px;height:28px;object-fit:contain;">
        ${nameLabel || last4Display ? `<span>${nameLabel}${last4Display}</span>` : ""}
      </span>
    `;
  }

  function formatMontant(value, currency) {
    return value === null || value === undefined
      ? "-"
      : `${Number(value).toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${currency}`;
  }

  // Part Xepay réelle = commission globale (t.commission_xepay, qui inclut
  // le StripeFee dedans) moins le StripeFee lui-même - jamais exposée comme
  // champ séparé par le backend, donc calculée ici à l'affichage.
  function xepayShare(t) {
    return t.commission_xepay == null || t.stripe_fee == null
      ? null
      : t.commission_xepay - t.stripe_fee;
  }

  
  function renderPaymentRow(t, i) {
    const currency = t.currency_gross ?? "USD";
    const canRefund = t.status === "paid" && t.payment_id;
    return `
      <tr>
        <td onclick="voirDetailActivite(${i})" style="cursor:pointer;">
          ${t.client_email ?? "-"}
        </td>
        <td onclick="voirDetailActivite(${i})" style="cursor:pointer;">
          ${paymentMethodIcon(
            t.details?.payment_method_type,
            t.details?.card_brand,
            t.details?.card_last4
          )}
        </td>
        <td onclick="voirDetailActivite(${i})" style="cursor:pointer;">
          ${paymentSourceLabel[t.source] ?? "-"}
        </td>
        <td class="amount-cell" onclick="voirDetailActivite(${i})">
          ${formatMontant(t.amount_gross, currency)}
        </td>
        <td class="amount-cell" onclick="voirDetailActivite(${i})">
          ${formatMontant(t.commission_xepay, currency)}
        </td>
        <td class="amount-cell" onclick="voirDetailActivite(${i})">
          ${formatMontant(xepayShare(t), currency)}
        </td>
        <td class="amount-cell" onclick="voirDetailActivite(${i})">
          ${formatMontant(t.stripe_fee, currency)}
        </td>
        <td class="amount-cell" onclick="voirDetailActivite(${i})">
          ${formatMontant(t.amount_net_merchant, currency)}
        </td>
        <td style="color:#6b7280;font-size:.85rem;">
          ${t.date && !isNaN(new Date(t.date))
            ? new Date(t.date).toLocaleDateString("fr-FR", {
                day: "2-digit",
                month: "short",
                year: "numeric",
                hour: "2-digit",
                minute: "2-digit"
              })
            : "N/A"}
        </td>
        <td style="color:#6b7280;font-size:.85rem;">
          ${t.details?.available_at && !isNaN(new Date(t.details.available_at))
            ? new Date(t.details.available_at).toLocaleDateString("fr-FR", {
                day: "2-digit",
                month: "short",
                year: "numeric",
                hour: "2-digit",
                minute: "2-digit"
              })
            : "-"}
        </td>
        <td>
          <span class="status-pill ${statusBadgeClass(t.status)}">
            ${statusMap[String(t.status).toLowerCase()] || t.status}
          </span>
        </td>
        <td>
          <button
            type="button"
            class="btn btn-export action-menu-trigger js-action-menu-toggle"
            data-index="${i}"
            data-can-refund="${canRefund ? "1" : "0"}"
            data-payment-id="${t.payment_id ?? ""}"
            data-amount="${t.amount_gross ?? 0}"
            data-currency="${currency}"
            title="Actions"
          >
            <i class="bi bi-three-dots"></i>
          </button>
        </td>
      </tr>
    `;
  }
  const payoutMethodLabel = { standard: "Standard", instant: "Instantané" };

  function renderWithdrawalRow(t, i) {
    const currency = (t.currency ?? "usd").toLowerCase();
    const zeroDecimalCurrencies = [
      "bif", "clp", "djf", "gnf", "jpy", "kmf",
      "krw", "pyg", "rwf", "ugx", "vnd", "vuv",
      "xaf", "xof", "xpf"
    ];
    const amount = Number(t.amount ?? 0) /

    (zeroDecimalCurrencies.includes(currency) ? 1 : 100);
    const statusLabels = {
      pending: "En attente",
      in_transit: "En cours",
      paid: "Réussi",
      failed: "Échoué",
      canceled: "Annulé"
    };
    const payoutDate = t.created
      ? new Date(t.created * 1000)
      : null;
    const dateDisplay =
      payoutDate && !isNaN(payoutDate)
        ? payoutDate.toLocaleString("fr-FR")
        : "N/A";
    return `
      <tr onclick="voirDetailActivite(${i})" style="cursor:pointer;">
        <td>${t.id ?? "-"}</td>
        <td>${payoutMethodLabel[t.method] ?? t.method ?? "-"}</td>
        <td class="amount-cell">
          ${formatMontant(amount, currency.toUpperCase())}
        </td>
        <td>
          <span class="status-pill ${statusBadgeClass(t.status)}">
            ${statusLabels[t.status] ?? t.status ?? "-"}
          </span>
        </td>
        <td style="color: #6b7280; font-size: 0.85rem;">
          ${t.failure_message ?? t.failure_code ?? "-"}
        </td>
        <td style="color: #6b7280; font-size: 0.85rem;">
          ${dateDisplay}
        </td>
      </tr>
    `;
  }

  function renderGenericRow(t, i) {
    const amount = t.amount_local ?? t.amount;
    const currency = t.currency_local ?? t.currency;
    const displayName = t.type === "payment" ? t.label || "Client" : t.label || "Retrait";
    const color = avatarColor(displayName || "x");
    return `
      <tr onclick="voirDetailActivite(${i})" style="cursor:pointer;">
        <td>
          <div class="d-flex align-items-center gap-3">
            <div class="avatar" style="background:${color};">${t.type === "payment" ? (displayName ? displayName[0].toUpperCase() : "?") : `<i class="bi ${typeIcon[t.type] || "bi-bank"}"></i>`}</div>
            <div><div class="fw-semibold">${displayName}</div><small style="color: #9ca3af; font-size:0.75rem;">${t.type === "payment" ? "Client" : "Retrait"}</small></div>
          </div>
        </td>
        <td><span class="amount-cell">${amount.toLocaleString("fr-FR")}</span><span class="amount-currency">${currency}</span></td>
        <td><span class="status-pill ${statusBadgeClass(t.status)}">${statusMap[t.status] || t.status}</span></td>
        <td style="color: #6b7280; font-size: 0.85rem;">${t.date && !isNaN(new Date(t.date)) ? new Date(t.date).toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "N/A"}</td>
      </tr>
    `;
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
      .map((t, i) =>
        currentType === "payment"
          ? renderPaymentRow(t, i)
          : currentType === "withdraw"
          ? renderWithdrawalRow(t, i)
          : renderGenericRow(t, i)
      )
      .join("");
    tbody.innerHTML =  html;
  }

  function voirDetailActivite(index) {
    const t = transactions[index];
    if (!t) return;
    const workspaceId = getWorkspaceId() || "me";
    if (t.type === "payment" && t.payment_id) {
      navigate(`/dash/workspace/${encodeURIComponent(workspaceId)}/transactions/paiements/py/${encodeURIComponent(t.payment_id)}`);
      return;
    }
    if (t.type === "withdraw" && t.withdrawal_id) {
      navigate(`/dash/workspace/${encodeURIComponent(workspaceId)}/transactions/retraits/wd/${encodeURIComponent(t.withdrawal_id)}`);
      return;
    }
  }
  // Filtre KPI -> statut(s) réel(s) envoyé(s) à /activity (voir
  // chargerTransactions). "" = pas de filtre (Tous). "Contestés" et "Non
  // capturés" n'ont pas d'équivalent dans Payment.status aujourd'hui (seul
  // Stripe le sait, via charge.disputed/charge.captured) : leur compteur
  // vaut donc 0 par construction, ce n'est pas un bug d'affichage.
  const PAYMENT_KPI_STATUS_MAP = {
    all: "",
    paid: "paid",
    refunded: "refunded,partially_refunded",
    disputed: "disputed",
    expired: "expired",
    uncaptured: "uncaptured",
  };

  async function loadPaymentsKpiSummary() {
    const summaryEl = document.getElementById("payments-kpi-summary");
    if (!summaryEl) return;
    try {
      // /activity charge déjà TOUT en mémoire côté backend avant de
      // paginer (cf. routes/payments.py:get_activity) : demander une limite
      // large ici ne coûte rien de plus et donne des compteurs exacts, sans
      // toucher à la pagination normale du tableau.
      const res = await apiFetch("/activity?type=payment&limit=100000");
      const data = await res.json();
      if (!res.ok) throw new Error("Impossible de récupérer les paiements");
      const allPayments = Array.isArray(data) ? data : [];

      const countFor = (statusValue) => {
        if (!statusValue) return allPayments.length;
        const wanted = statusValue.split(",");
        return allPayments.filter((p) => wanted.includes(p.status)).length;
      };

      const activeFilter =
        Object.keys(PAYMENT_KPI_STATUS_MAP).find(
          (key) => PAYMENT_KPI_STATUS_MAP[key] === kpiPaymentStatus
        ) || "all";

      renderCommerceKpis(
        summaryEl,
        [
          { filter: "all", label: "Tous", count: countFor(PAYMENT_KPI_STATUS_MAP.all) },
          { filter: "paid", label: "Réussis", count: countFor(PAYMENT_KPI_STATUS_MAP.paid) },
          { filter: "refunded", label: "Remboursés", count: countFor(PAYMENT_KPI_STATUS_MAP.refunded) },
          { filter: "disputed", label: "Contestés", count: countFor(PAYMENT_KPI_STATUS_MAP.disputed) },
          { filter: "expired", label: "En échec", count: countFor(PAYMENT_KPI_STATUS_MAP.expired) },
          { filter: "uncaptured", label: "Non capturés", count: countFor(PAYMENT_KPI_STATUS_MAP.uncaptured) },
        ],
        activeFilter,
        (filter) => {
          kpiPaymentStatus = PAYMENT_KPI_STATUS_MAP[filter] || "";
          offset = 0;
          pageNumber = 1;
          hasNextPage = true;
          transactions = [];
          updatePagination();
          chargerTransactions();
        }
      );
    } catch (err) {
      console.error("Erreur chargement KPI paiements :", err);
    }
  }

  function updatePaymentsViewMode() {
    const isPayments = currentType === "payment";
    const extraFiltersWrap = document.getElementById("pay-more-filters-wrap");
    if (extraFiltersWrap) extraFiltersWrap.style.display = isPayments ? "block" : "none";
    const kpiSummaryEl = document.getElementById("payments-kpi-summary");
    if (kpiSummaryEl) {
      kpiSummaryEl.style.display = isPayments ? "block" : "none";
      if (isPayments) {
        loadPaymentsKpiSummary();
      } else {
        kpiPaymentStatus = "";
      }
    }
  }
  async function chargerTransactions() {
    if (isLoading) return;
    isLoading = true;
    const loader = document.getElementById("loading-more");
    if (loader) loader.classList.remove("d-none");
    try {
      const statut = document.getElementById("filter-statut").value;
      const params = new URLSearchParams({ offset, limit });
      if (currentType) params.append("type", currentType);
      // Le filtre KPI Paiements (voir kpiPaymentStatus) prend le pas sur le
      // select/les chips de statut existants quand il est actif.
      const effectiveStatus = kpiPaymentStatus || statut;
      if (effectiveStatus) params.append("status", effectiveStatus);
      // Filtres avancés : uniquement pertinents et envoyés sur l'onglet
      // Paiements (jamais sur Retraits/Tous).
      if (currentType === "payment") {
        const startDate = document.getElementById("startDate").value;
        const endDate = document.getElementById("endDate").value;
        const minAmount = document.getElementById("pay-min-amount").value;
        const maxAmount = document.getElementById("pay-max-amount").value;
        const currency = document.getElementById("pay-currency").value;
        const paymentMethod = document.getElementById("pay-payment-method").value;
        if (startDate) params.append("start_date", startDate);
        if (endDate) params.append("end_date", endDate);
        if (minAmount) params.append("min_amount", minAmount);
        if (maxAmount) params.append("max_amount", maxAmount);
        if (currency) params.append("currency", currency);
        if (paymentMethod) params.append("payment_method", paymentMethod);
      }
      let res;
      let data;
      if (currentType === "withdraw") {
        res = await apiFetch("/withdrawals");
        const result = await res.json();
        console.log("DATA payout: ", result)
        data = result.payouts ?? result;
      } else {
        res = await apiFetch(`/activity?${params}`);
        data = await res.json();
      }
      if (!res.ok) {
        throw new Error(`Erreur HTTP ${res.status}`);
      }
      if (!Array.isArray(data)) {
        data = data.payouts ?? data.transactions ?? [];
      }
      transactions = data;
      afficherTransactions(transactions);
      hasNextPage = data.length === limit;
      updatePagination();
    } catch (err) {
      console.error("Erreur activity:", err);
    }
    isLoading = false;
    if (loader) {
      loader.classList.add("d-none");
    }
  }
  // --- Menu Action "..." (Rembourser / Détails du paiement) ---
  const actionMenuEl = document.getElementById("payment-action-menu");
  let actionMenuTriggerBtn = null;

  function closeActionMenu() {
    actionMenuEl.classList.remove("open");
    actionMenuTriggerBtn = null;
  }

  function openActionMenu(triggerBtn) {
    actionMenuTriggerBtn = triggerBtn;
    const canRefund = triggerBtn.dataset.canRefund === "1";
    const refundItem = actionMenuEl.querySelector('[data-action="refund"]');
    refundItem.disabled = !canRefund;
    refundItem.title = canRefund ? "" : "Remboursement indisponible pour ce paiement";
    actionMenuEl.classList.add("open");
    // Positionné en fixed sous le bouton cliqué, aligné à droite — recalculé
    // à chaque ouverture, jamais ancré dans le DOM du tableau (voir
    // commentaire sur ACTION_MENU_HTML : évite le clipping par
    // #transactions-scroll-box/.table-wrap).
    const rect = triggerBtn.getBoundingClientRect();
    const menuRect = actionMenuEl.getBoundingClientRect();
    let top = rect.bottom + 4;
    if (top + menuRect.height > window.innerHeight) {
      top = rect.top - menuRect.height - 4;
    }
    let left = rect.right - menuRect.width;
    if (left < 4) left = 4;
    actionMenuEl.style.top = `${top}px`;
    actionMenuEl.style.left = `${left}px`;
  }

  on(document.getElementById("tbody-transactions"), "click", (event) => {
    const toggleBtn = event.target.closest(".js-action-menu-toggle");
    if (toggleBtn) {
      if (actionMenuTriggerBtn === toggleBtn) {
        closeActionMenu();
      } else {
        openActionMenu(toggleBtn);
      }
    }
  });
  on(document, "click", (event) => {
    if (!actionMenuTriggerBtn) return;
    if (event.target.closest("#payment-action-menu") || event.target.closest(".js-action-menu-toggle")) return;
    closeActionMenu();
  });
  on(window, "scroll", () => closeActionMenu());
  on(window, "resize", () => closeActionMenu());
  on(document, "keydown", (event) => {
    if (event.key === "Escape") closeActionMenu();
  });

  async function refundPayment(paymentId, amount, currency) {
    if (!confirm(
      `Confirmer le remboursement du paiement de ${amount} ${currency} ?`
    )) return;
    try {
      const res = await apiFetch(
        `/payments/${encodeURIComponent(paymentId)}/refund`,
        { method: "POST", body: {} }
      );
      const data = await res.json();
      if (!res.ok) {
        showToast(
          typeof data.detail === "string"
            ? data.detail
            : "Impossible d'effectuer le remboursement",
          "error"
        );
        return;
      }
      showToast(
        data.status === "succeeded"
          ? "Remboursement confirmé par Stripe"
          : `Demande de remboursement transmise à Stripe (${data.status})`,
        "success"
      );
      offset = 0;
      transactions = [];
      document.getElementById("tbody-transactions").innerHTML = "";
      await chargerTransactions();
      // Le remboursement change le statut du paiement (paid -> refunded) :
      // les compteurs KPI doivent refléter ce changement immédiatement.
      if (currentType === "payment") await loadPaymentsKpiSummary();
    } catch (error) {
      console.error("Erreur remboursement :", error);
      showToast("Erreur de connexion au serveur", "error");
    }
  }

  // --- Tiroir "Détails du paiement" (même gabarit que Clients/Produits,
  // voir views/commerce.js) : rempli directement depuis l'objet déjà en
  // mémoire (transactions[index], issu de /activity), sans appel réseau
  // supplémentaire. ---
  const paymentDetailsContentEl = document.getElementById("payment-details-content");
  const paymentDetailsSubtitleEl = document.getElementById("payment-details-subtitle");

  function detailRow(label, value) {
    return `
      <div class="customer-detail-item">
        <span>${label}</span>
        <strong>${value ?? "-"}</strong>
      </div>
    `;
  }

  function detailIdRow(label, value) {
    return `
      <div class="customer-detail-item">
        <span>${label}</span>
        <strong>${value ? `Id : ${value}` : "-"}</strong>
      </div>
    `;
  }

  // Même format que la colonne Date du tableau (voir renderPaymentRow) -
  // pour que la modal et la liste affichent la date de façon cohérente.
  function formatDateLikeTable(value) {
    if (!value || isNaN(new Date(value))) return null;
    return new Date(value).toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    });
  }

  function showPaymentDetails(t) {
    const currency = t.currency_gross ?? "USD";
    const d = t.details || {};
    const avatarInitial = (t.client_email || "?")[0].toUpperCase();
    paymentDetailsSubtitleEl.textContent = t.client_email || t.payment_id || "";
    paymentDetailsContentEl.innerHTML = `
      <div class="customer-profile">
        <div class="customer-profile-avatar">${avatarInitial}</div>
        <div>
          <h4>${t.client_email ?? "Client"}</h4>
          <code>${t.payment_id ?? "-"}</code>
        </div>
      </div>
      <div class="customer-details-grid">
        ${detailIdRow("Lien de paiement", d.link_id)}
        ${detailRow("Montant brut", formatMontant(t.amount_gross, currency))}
        ${detailRow("Commission globale", formatMontant(t.commission_xepay, currency))}
        ${detailRow("Commission Xepay", formatMontant(xepayShare(t), currency))}
        ${detailRow("Frais Stripe", formatMontant(t.stripe_fee, currency))}
        ${detailRow("Montant net marchand", formatMontant(t.amount_net_merchant, currency))}
        ${detailRow("Statut", statusMap[String(t.status).toLowerCase()] || t.status)}
        ${detailRow("Date", formatDateLikeTable(t.date) ?? "N/A")}
        ${detailRow("Disponible le", formatDateLikeTable(d.available_at) ?? "-")}
        ${detailRow("Moyen de paiement", paymentMethodIcon(d.payment_method_type, d.card_brand, d.card_last4))}
        ${detailRow("Expiration carte", d.card_exp_month && d.card_exp_year ? `${d.card_exp_month}/${d.card_exp_year}` : "-")}
        ${detailRow("Session Stripe", d.stripe_session_id)}
        ${detailIdRow("Référence de la transaction", d.stripe_payment_intent_id)}
        ${detailIdRow("Compte Stripe", d.stripe_account_id)}
      </div>
      ${renderMetadataSection(d.metadata, "Paiement")}
    `;
    paymentDetailsModal.classList.add("open");
  }

  on(actionMenuEl, "click", (event) => {
    const item = event.target.closest(".action-menu-item");
    if (!item || item.disabled || !actionMenuTriggerBtn) return;
    const triggerBtn = actionMenuTriggerBtn;
    const index = Number(triggerBtn.dataset.index);
    const t = transactions[index];
    closeActionMenu();
    if (item.dataset.action === "refund") {
      const paymentId = triggerBtn.dataset.paymentId;
      if (!paymentId) {
        showToast("Identifiant du paiement introuvable", "error");
        return;
      }
      refundPayment(paymentId, triggerBtn.dataset.amount, triggerBtn.dataset.currency || "USD");
    } else if (item.dataset.action === "details") {
      if (!t) return;
      showPaymentDetails(t);
    }
  });
  on(document.getElementById("close-payment-details"), "click", () => {
    paymentDetailsModal.classList.remove("open");
  });
  on(paymentDetailsModal, "click", (event) => {
    if (event.target === paymentDetailsModal) paymentDetailsModal.classList.remove("open");
  });
  async function rafraichir(btn) {
    try {
      btn.style.transition = "transform 0.6s linear";
      btn.style.transform = "rotate(360deg)";
      btn.disabled = true;
      await chargerTransactions();
      await loadStats();
      if (currentType === "payment") await loadPaymentsKpiSummary();
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
    updateTableHead();
    updatePaymentsViewMode();
    offset = 0;
    pageNumber = 1;
    hasNextPage = true;
    transactions = [];
    updatePagination();
    chargerTransactions();
  }

  function renderStats(stats) {
    // stats.total_received est stocké en XOF côté backend - converti vers
    // la devise choisie dans le sélecteur de la vue Accueil (core/
    // currency.js, lu ici au montage ; cette vue n'a pas son propre
    // sélecteur, voir la conversation produit du 2026-10-25).
    const currency = getCurrency();
    document.getElementById("total-xof").innerText = formatMoney((stats.total_received || 0) * getRate("XOF", currency), currency);
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
    if (paidEl) paidEl.innerText = `Sur un maximum de ${linksLimitText} liens offert`;
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
  on(document.getElementById("filter-statut"), "change", () => {
    offset = 0;
    pageNumber = 1;
    hasNextPage = true;
    transactions = [];
    updatePagination();
    chargerTransactions();
  });
  // --- Pagination : boutons précédent / suivant
  on(document.getElementById("next-page"), "click", async () => {
    if (isLoading || !hasNextPage) return;
    pageNumber++;
    offset = (pageNumber - 1) * limit;
    await chargerTransactions();
  });
  on(document.getElementById("prev-page"), "click", async () => {
    if (isLoading || pageNumber <= 1) return;
    pageNumber--;
    offset = (pageNumber - 1) * limit;
    await chargerTransactions();
  });
  function relancerPaiements() {
    offset = 0;
    pageNumber = 1;
    hasNextPage = true;
    transactions = [];
    updatePagination();
    chargerTransactions();
  }
  on(document.getElementById("startDate"), "change", relancerPaiements);
  on(document.getElementById("endDate"), "change", relancerPaiements);
  on(document.getElementById("pay-min-amount"), "change", relancerPaiements);
  on(document.getElementById("pay-max-amount"), "change", relancerPaiements);
  on(document.getElementById("pay-currency"), "change", relancerPaiements);
  on(document.getElementById("pay-payment-method"), "change", relancerPaiements);
  on(document.getElementById("payMoreFiltersBtn"), "click", () => {
    const row = document.getElementById("payMoreFiltersRow");
    row.style.display = row.style.display === "none" ? "flex" : "none";
  });
  on(document.getElementById("exportFinancialReportBtn"), "click", initStripeBalanceReport);
  on(document.getElementById("exportBtn"), "click", exportCSV);
  on(document.getElementById("exportPdfBtn"), "click", exportPDF);

  const successCard = document.getElementById("successCard");
  const chartTooltip = document.getElementById("chartTooltip");
  if (successCard && chartTooltip) {
    on(successCard, "mouseenter", () => (chartTooltip.style.display = "block"));
    on(successCard, "mouseleave", () => (chartTooltip.style.display = "none"));
  }
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

  // Page dédiée (fixedType) : masque le sélecteur de catégorie (rien à
  // basculer depuis ici), élargit la colonne de contenu, adapte le titre, et
  // applique l'état initial (updateTableHead/updatePaymentsViewMode ne sont
  // normalement déclenchées que par un clic sur un chip — ici il n'y en a
  // aucun puisque currentType est déjà figé dès la déclaration plus haut).
  if (fixedType) {
    const typeChipGroup = document.getElementById("type-chip-group");
    if (typeChipGroup) typeChipGroup.style.display = "none";
    container.querySelector(".dashboard-layout")?.classList.add("subview-mode");
    // KPI agrandis (15px) sur la page Paiements uniquement — Retraits
    // garde le gabarit .subview-mode standard.
    if (fixedType === "payment") container.querySelector(".dashboard-layout")?.classList.add("subview-payments");
    const titleEl = container.querySelector("#transactions-normal-view .page-title");
    const subtitleEl = container.querySelector("#transactions-normal-view .page-subtitle");
    const titleByType = { payment: ["fa-credit-card", "Paiements"], withdraw: ["fa-money-bill-transfer", "Retraits"] };
    const subtitleByType = {
      payment: "Historique de vos paiements",
      withdraw: "Historique de vos retraits",
    };
    const [iconClass, label] = titleByType[fixedType] || ["fa-credit-card", "Transactions"];
    if (titleEl) titleEl.innerHTML = `<i class="fa-solid ${iconClass}"></i> ${label}`;
    if (subtitleEl) subtitleEl.textContent = subtitleByType[fixedType] || "";
    // Retraits : uniquement le tableau d'historique — pas de KPI, pas de
    // boutons (export/Stripe/Retirer), pas de filtres.
    if (fixedType === "withdraw") {
      const kpiRowEl = document.getElementById("kpi-row");
      const exportActionsEl2 = document.getElementById("export-actions");
      const toolbarEl = container.querySelector(".toolbar");
      if (kpiRowEl) kpiRowEl.style.display = "none";
      if (exportActionsEl2) exportActionsEl2.style.display = "none";
      if (toolbarEl) toolbarEl.style.display = "none";
    }
    updateTableHead();
    updatePaymentsViewMode();
  }

  // window.upgrade est exposé globalement par app.js (modale partagée persistante)
  window.voirDetailActivite = voirDetailActivite;

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
    loadPlan();
  })();

  return {
    unmount() {
      const stripeReportModalEl = document.getElementById("stripeReportModal");
      const stripeReportModalInstance = stripeReportModalEl && bootstrap.Modal.getInstance(stripeReportModalEl);
      if (stripeReportModalInstance) {
        stripeReportModalInstance.hide();
        stripeReportModalInstance.dispose();
        document.body.classList.remove("modal-open");
        document.body.style.removeProperty("overflow");
        document.body.style.removeProperty("padding-right");
        document.querySelectorAll(".modal-backdrop").forEach((el) => el.remove());
      }
      stripeReportModalEl?.remove();
      document.getElementById("payment-action-menu")?.remove();
      if (statusChart) statusChart.destroy();
      boundListeners.forEach(({ target, type, fn }) => target.removeEventListener(type, fn));
      document.body.classList.remove("locked-page");
      delete window.voirDetailActivite;
    },
  };
}
