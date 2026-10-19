// Vue "Dashboard" (accueil) — ne garde plus que la section "Activité" :
// l'ancien contenu (solde, retrait, création de lien, liste des liens,
// bannières upgrade) a été retiré à la demande, cette vue n'affiche plus
// que les 6 blocs d'activité comparant une période à la précédente.
import { apiFetch } from "../core/apiClient.js";
import { setViewStyles } from "../core/styleLoader.js";

const TEMPLATE = `
<div class="activity-section mb-4">
  <div class="activity-section-head">
    <h5 class="fw-bold mb-0 text-muted">📊 Activité</h5>
    <div class="period-selector" id="period-selector">
      <button type="button" class="period-btn" data-period="7">7 jours</button>
      <button type="button" class="period-btn active" data-period="30">30 jours</button>
      <button type="button" class="period-btn" data-period="90">90 jours</button>
    </div>
  </div>
  <div class="activity-grid" id="activity-grid"></div>
</div>
`;

export async function mount(container) {
  await setViewStyles(["dashboard.css"]);
  container.innerHTML = TEMPLATE;

  const boundListeners = [];
  function on(target, type, fn) {
    target.addEventListener(type, fn);
    boundListeners.push({ target, type, fn });
  }

  /* =====================================================
     SECTION "ACTIVITÉ" — 6 blocs (clients, produits, solde,
     factures, abonnements, liens), comparant la période choisie
     (7/30/90 jours) à la période équivalente précédente.
  ===================================================== */

  const DAY_MS = 24 * 60 * 60 * 1000;

  // Les axes du graphe représentent toujours (revenus générés, période) —
  // jamais un nombre d'éléments. Le nombre reste affiché (countLabel), mais
  // seulement en texte à côté du chiffre clé, jamais comme donnée du graphe.
  const ACTIVITY_CONFIG = [
    { key: "clients", label: "Nouveaux clients", icon: "fa-user-plus", countLabel: "nouveaux clients" },
    { key: "products", label: "Nouveaux produits", icon: "fa-box", countLabel: "nouveaux produits" },
    { key: "balance", label: "Variation du solde", icon: "fa-wallet", countLabel: null },
    { key: "invoices", label: "Factures", icon: "fa-file-invoice", countLabel: "nouvelles factures" },
    { key: "subscriptions", label: "Abonnements", icon: "fa-rotate", countLabel: "nouveaux abonnements" },
    { key: "links", label: "Liens de paiement", icon: "fa-link", countLabel: "nouveaux liens" },
  ];

  let activityRaw = null;
  let activityDays = 30;
  const activityCharts = {};

  function activityCardHTML(cfg) {
    return `
      <div class="activity-card" data-key="${cfg.key}">
        <div class="activity-card-head">
          <span class="activity-card-icon"><i class="fa-solid ${cfg.icon}"></i></span>
          <span class="activity-card-title">${cfg.label}</span>
        </div>
        <div class="activity-card-metric">
          <span class="activity-value" id="activity-value-${cfg.key}">—</span>
          <span class="activity-delta" id="activity-delta-${cfg.key}"></span>
        </div>
        ${cfg.countLabel ? `<div class="activity-count" id="activity-count-${cfg.key}"></div>` : ""}
        <div class="activity-chart-wrap">
          <canvas id="activity-chart-${cfg.key}"></canvas>
        </div>
      </div>
    `;
  }

  // Unix (secondes, objets Stripe) ou ISO (nos propres endpoints) -> ms.
  function toTimestamp(raw) {
    if (raw == null) return null;
    if (typeof raw === "number") return raw * 1000;
    const t = new Date(raw).getTime();
    return Number.isNaN(t) ? null : t;
  }

  async function safeJson(settled) {
    if (settled.status !== "fulfilled" || !settled.value.ok) return null;
    try {
      return await settled.value.json();
    } catch {
      return null;
    }
  }

  async function fetchActivityRawData() {
    const [customersRes, productsRes, subscriptionsRes, invoicesRes, linksRes, walletRes] = await Promise.allSettled([
      apiFetch("/stripe/connect/customers"),
      apiFetch("/stripe/connect/products"),
      apiFetch("/stripe/connect/subscriptions"),
      apiFetch("/stripe/connect/invoices"),
      apiFetch("/links?limit=200&offset=0"),
      apiFetch("/wallet/history?limit=300"),
    ]);

    const customersData = await safeJson(customersRes);
    const productsData = await safeJson(productsRes);
    const subscriptionsData = await safeJson(subscriptionsRes);
    const invoicesData = await safeJson(invoicesRes);
    const linksData = await safeJson(linksRes);
    const walletData = await safeJson(walletRes);

    // "value" = revenu généré par l'élément (jamais un simple comptage) :
    // total dépensé par le client, prix du produit, montant de l'abonnement/
    // de la facture/du lien. Stripe renvoie ses montants en centimes (voir
    // le même /100 partout dans commerce.js) ; nos propres endpoints (liens,
    // wallet) sont déjà en unité pleine (XOF).
    return {
      clients: (customersData?.data || []).map((c) => ({ ts: toTimestamp(c.created), value: (c.total_spent || 0) / 100 })),
      products: (productsData?.data || []).map((p) => ({
        ts: toTimestamp(p.created),
        value: (p.prices?.[0]?.unit_amount || 0) / 100,
      })),
      subscriptions: (subscriptionsData?.data || []).map((s) => {
        const item = s.items?.data?.[0];
        const unitAmount = item?.price?.unit_amount || 0;
        const quantity = item?.quantity || 1;
        return { ts: toTimestamp(s.created), value: (unitAmount * quantity) / 100 };
      }),
      invoices: (invoicesData?.data || []).map((i) => ({
        ts: toTimestamp(i.created),
        value: (i.amount_paid || i.amount_due || 0) / 100,
      })),
      links: (Array.isArray(linksData) ? linksData : []).map((l) => ({ ts: toTimestamp(l.created_at), value: l.amount || 0 })),
      balance: (walletData?.transactions || []).map((t) => ({
        ts: toTimestamp(t.created_at),
        value: t.direction === "out" ? -Math.abs(t.amount) : Math.abs(t.amount),
      })),
    };
  }

  function computeActivityStats(items, days) {
    const now = Date.now();
    const currentStart = now - days * DAY_MS;
    const previousStart = now - 2 * days * DAY_MS;
    const currentDaily = new Array(days).fill(0);
    const previousDaily = new Array(days).fill(0);
    let currentTotal = 0;
    let previousTotal = 0;
    let currentCount = 0;
    let previousCount = 0;

    items.forEach(({ ts, value }) => {
      if (ts == null) return;
      if (ts >= currentStart && ts <= now) {
        const idx = Math.min(days - 1, Math.max(0, Math.floor((ts - currentStart) / DAY_MS)));
        currentDaily[idx] += value;
        currentTotal += value;
        currentCount += 1;
      } else if (ts >= previousStart && ts < currentStart) {
        const idx = Math.min(days - 1, Math.max(0, Math.floor((ts - previousStart) / DAY_MS)));
        previousDaily[idx] += value;
        previousTotal += value;
        previousCount += 1;
      }
    });

    return { currentDaily, previousDaily, currentTotal, previousTotal, currentCount, previousCount };
  }

  function buildActivityLabels(days) {
    const now = new Date();
    const labels = [];
    for (let i = days - 1; i >= 0; i--) {
      const d = new Date(now.getTime() - i * DAY_MS);
      labels.push(d.toLocaleDateString("fr-FR", { day: "2-digit", month: "short" }));
    }
    return labels;
  }

  function formatActivityValue(value) {
    return Math.round(value).toLocaleString("fr-FR") + " XOF";
  }

  // Indicateur de pourcentage (hausse/baisse) avec code couleur, basé sur
  // les revenus (jamais sur un nombre d'éléments) : vert = hausse, rouge =
  // baisse, gris = stable/pas de référence. Math.abs(previousTotal) au
  // dénominateur évite qu'un total précédent négatif (solde en baisse)
  // n'inverse artificiellement le signe du pourcentage affiché.
  function renderActivityDelta(el, currentTotal, previousTotal) {
    if (previousTotal === 0) {
      if (currentTotal === 0) {
        el.textContent = "—";
        el.className = "activity-delta flat";
      } else {
        el.textContent = "Nouveau";
        el.className = "activity-delta up";
      }
      return;
    }
    const pct = ((currentTotal - previousTotal) / Math.abs(previousTotal)) * 100;
    const sign = pct > 0 ? "+" : "";
    el.textContent = `${sign}${pct.toFixed(0)}% vs précédent`;
    el.className = "activity-delta " + (pct > 0 ? "up" : pct < 0 ? "down" : "flat");
  }

  function renderActivityCard(cfg, items, days) {
    const { currentDaily, previousDaily, currentTotal, previousTotal, currentCount } = computeActivityStats(items || [], days);
    const valueEl = document.getElementById(`activity-value-${cfg.key}`);
    const deltaEl = document.getElementById(`activity-delta-${cfg.key}`);
    if (valueEl) valueEl.textContent = formatActivityValue(currentTotal);
    if (deltaEl) renderActivityDelta(deltaEl, currentTotal, previousTotal);

    if (cfg.countLabel) {
      const countEl = document.getElementById(`activity-count-${cfg.key}`);
      if (countEl) countEl.textContent = `${currentCount.toLocaleString("fr-FR")} ${cfg.countLabel}`;
    }

    const canvas = document.getElementById(`activity-chart-${cfg.key}`);
    if (!canvas) return;
    const labels = buildActivityLabels(days);

    if (activityCharts[cfg.key]) {
      const chart = activityCharts[cfg.key];
      chart.data.labels = labels;
      chart.data.datasets[0].data = currentDaily;
      chart.data.datasets[1].data = previousDaily;
      chart.update();
      return;
    }

    activityCharts[cfg.key] = new Chart(canvas.getContext("2d"), {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Période actuelle",
            data: currentDaily,
            borderColor: "#eab308",
            backgroundColor: "rgba(234,179,8,0.1)",
            borderWidth: 2,
            pointRadius: 0,
            pointHoverRadius: 4,
            tension: 0.3,
            fill: true,
          },
          {
            label: "Période précédente",
            data: previousDaily,
            borderColor: "#9ca3af",
            borderDash: [4, 4],
            borderWidth: 2,
            pointRadius: 0,
            pointHoverRadius: 4,
            tension: 0.3,
            fill: false,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: {
            position: "top",
            align: "end",
            labels: { boxWidth: 12, boxHeight: 2, color: "#6b7280", font: { size: 11 } },
          },
          tooltip: {
            callbacks: {
              label: (ctx) => `${ctx.dataset.label}: ${formatActivityValue(ctx.parsed.y)}`,
            },
          },
        },
        scales: {
          x: {
            title: { display: true, text: "Période (jour)", color: "#6b7280", font: { size: 11, weight: "600" } },
            grid: { display: false },
            ticks: { color: "#9ca3af", font: { size: 10 }, maxRotation: 0, autoSkip: true },
          },
          y: {
            title: { display: true, text: "Revenus générés (XOF)", color: "#6b7280", font: { size: 11, weight: "600" } },
            beginAtZero: true,
            grid: { color: "#e5e7eb" },
            ticks: {
              color: "#9ca3af",
              font: { size: 10 },
              callback: (val) => Number(val).toLocaleString("fr-FR"),
            },
          },
        },
      },
    });
  }

  function renderAllActivityCards() {
    if (!activityRaw) return;
    ACTIVITY_CONFIG.forEach((cfg) => renderActivityCard(cfg, activityRaw[cfg.key], activityDays));
  }

  async function initActivitySection() {
    const grid = document.getElementById("activity-grid");
    if (!grid) return;
    grid.innerHTML = ACTIVITY_CONFIG.map(activityCardHTML).join("");

    document.querySelectorAll(".period-btn").forEach((btn) => {
      on(btn, "click", () => {
        document.querySelectorAll(".period-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        activityDays = Number(btn.dataset.period);
        renderAllActivityCards();
      });
    });

    activityRaw = await fetchActivityRawData();
    renderAllActivityCards();
  }

  initActivitySection();

  return {
    unmount() {
      Object.values(activityCharts).forEach((chart) => chart.destroy());
      boundListeners.forEach(({ target, type, fn }) => target.removeEventListener(type, fn));
    },
  };
}
