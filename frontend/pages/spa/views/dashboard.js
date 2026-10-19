// Vue "Dashboard" (accueil) — section "Activité" uniquement : pour chaque
// catégorie (clients, produits, solde, factures, abonnements, liens), deux
// blocs côte à côte — un pour les revenus générés, un pour le nombre
// d'éléments — chacun avec sa propre courbe (période actuelle vs
// précédente), alignés 2 par 2. Les revenus sont affichés dans la devise
// choisie (USD par défaut), convertis à la volée via /rates.
import { apiFetch } from "../core/apiClient.js";
import { setViewStyles } from "../core/styleLoader.js";

const TEMPLATE = `
<div class="activity-section mb-4">
  <div class="activity-section-head">
    <h5 class="fw-bold mb-0 text-muted">📊 Activité</h5>
    <div class="activity-controls">
      <select class="currency-select" id="activity-currency">
        <option value="USD" selected>USD</option>
        <option value="EUR">EUR</option>
        <option value="XOF">XOF</option>
      </select>
      <div class="period-selector" id="period-selector">
        <button type="button" class="period-btn" data-period="7">7 jours</button>
        <button type="button" class="period-btn active" data-period="30">30 jours</button>
        <button type="button" class="period-btn" data-period="90">90 jours</button>
      </div>
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
     SECTION "ACTIVITÉ" — 6 catégories × 2 blocs (revenus, nombre),
     comparant la période choisie (7/30/90 jours) à la période
     équivalente précédente. sourceCurrency = devise dans laquelle le
     montant brut de la catégorie est exprimé avant conversion :
     Stripe (clients/produits/abonnements/factures) renvoie en USD sur ce
     compte ; nos propres endpoints (liens, wallet) sont en XOF.
  ===================================================== */

  const DAY_MS = 24 * 60 * 60 * 1000;

  const ACTIVITY_CATEGORIES = [
    { key: "clients", label: "Nouveaux clients", icon: "fa-user-plus", sourceCurrency: "USD" },
    { key: "products", label: "Nouveaux produits", icon: "fa-box", sourceCurrency: "USD" },
    { key: "balance", label: "Variation du solde", icon: "fa-wallet", sourceCurrency: "XOF" },
    { key: "invoices", label: "Factures", icon: "fa-file-invoice", sourceCurrency: "USD" },
    { key: "subscriptions", label: "Abonnements", icon: "fa-rotate", sourceCurrency: "USD" },
    { key: "links", label: "Liens de paiement", icon: "fa-link", sourceCurrency: "XOF" },
  ];

  let activityRaw = null;
  let activityDays = 30;
  let activityCurrency = "USD";
  const activityCharts = {};
  const rateCache = {};

  function activityCardId(cat, kind) {
    return `${cat.key}-${kind}`;
  }

  function activityCardHTML(cat, kind) {
    const id = activityCardId(cat, kind);
    const title = kind === "revenue" ? `${cat.label} — Revenus` : `${cat.label} — Nombre`;
    return `
      <div class="activity-card" data-key="${id}">
        <div class="activity-card-head">
          <span class="activity-card-icon"><i class="fa-solid ${cat.icon}"></i></span>
          <span class="activity-card-title">${title}</span>
        </div>
        <div class="activity-card-metric">
          <span class="activity-value" id="activity-value-${id}">—</span>
          <span class="activity-delta" id="activity-delta-${id}"></span>
        </div>
        <div class="activity-chart-wrap">
          <canvas id="activity-chart-${id}"></canvas>
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

    // "value" = revenu généré par l'élément, dans sa sourceCurrency (jamais
    // un simple comptage, qui est dérivé séparément à l'affichage) : total
    // dépensé par le client, prix du produit, montant de l'abonnement/de la
    // facture/du lien. Stripe renvoie ses montants en centimes (voir le même
    // /100 partout dans commerce.js) ; nos propres endpoints (liens, wallet)
    // sont déjà en unité pleine (XOF).
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

  // Taux de change avec cache mémoire (le choix de devise ne redéclenche
  // que 2 appels réseau max — une sourceCurrency par Stripe/nos endpoints —
  // jamais un appel par catégorie). Repli sur 1 (pas de conversion) si le
  // taux est indisponible, pour ne jamais casser l'affichage.
  async function getRate(from, to) {
    if (from === to) return 1;
    const cacheKey = `${from}_${to}`;
    if (rateCache[cacheKey] != null) return rateCache[cacheKey];
    try {
      const res = await apiFetch(`/rates?from_currency=${from}&to_currency=${to}`);
      if (!res.ok) return 1;
      const data = await res.json();
      rateCache[cacheKey] = data.rate;
      return data.rate;
    } catch {
      return 1;
    }
  }

  function computeActivityStats(items, days) {
    const now = Date.now();
    const currentStart = now - days * DAY_MS;
    const previousStart = now - 2 * days * DAY_MS;
    const currentRevenueDaily = new Array(days).fill(0);
    const previousRevenueDaily = new Array(days).fill(0);
    const currentCountDaily = new Array(days).fill(0);
    const previousCountDaily = new Array(days).fill(0);
    let currentTotal = 0;
    let previousTotal = 0;
    let currentCount = 0;
    let previousCount = 0;

    items.forEach(({ ts, value }) => {
      if (ts == null) return;
      if (ts >= currentStart && ts <= now) {
        const idx = Math.min(days - 1, Math.max(0, Math.floor((ts - currentStart) / DAY_MS)));
        currentRevenueDaily[idx] += value;
        currentCountDaily[idx] += 1;
        currentTotal += value;
        currentCount += 1;
      } else if (ts >= previousStart && ts < currentStart) {
        const idx = Math.min(days - 1, Math.max(0, Math.floor((ts - previousStart) / DAY_MS)));
        previousRevenueDaily[idx] += value;
        previousCountDaily[idx] += 1;
        previousTotal += value;
        previousCount += 1;
      }
    });

    return {
      currentRevenueDaily,
      previousRevenueDaily,
      currentCountDaily,
      previousCountDaily,
      currentTotal,
      previousTotal,
      currentCount,
      previousCount,
    };
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

  function formatMoney(value, currency) {
    return Math.round(value).toLocaleString("fr-FR") + " " + currency;
  }

  function formatCount(value) {
    return Math.round(value).toLocaleString("fr-FR");
  }

  function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  // Indicateur de pourcentage (hausse/baisse) avec code couleur : vert =
  // hausse, rouge = baisse, gris = stable/pas de référence. Math.abs(previous)
  // au dénominateur évite qu'une valeur précédente négative (solde en
  // baisse) n'inverse artificiellement le signe du pourcentage affiché.
  function setDelta(id, current, previous) {
    const el = document.getElementById(id);
    if (!el) return;
    if (previous === 0) {
      if (current === 0) {
        el.textContent = "—";
        el.className = "activity-delta flat";
      } else {
        el.textContent = "Nouveau";
        el.className = "activity-delta up";
      }
      return;
    }
    const pct = ((current - previous) / Math.abs(previous)) * 100;
    const sign = pct > 0 ? "+" : "";
    el.textContent = `${sign}${pct.toFixed(0)}% vs précédent`;
    el.className = "activity-delta " + (pct > 0 ? "up" : pct < 0 ? "down" : "flat");
  }

  function renderOrUpdateChart(id, labels, currentData, previousData, valueFormatter, yAxisLabel) {
    const canvas = document.getElementById(`activity-chart-${id}`);
    if (!canvas) return;

    if (activityCharts[id]) {
      const chart = activityCharts[id];
      chart.data.labels = labels;
      chart.data.datasets[0].data = currentData;
      chart.data.datasets[1].data = previousData;
      chart.options.scales.y.title.text = yAxisLabel;
      chart.options.plugins.tooltip.callbacks.label = (ctx) => `${ctx.dataset.label}: ${valueFormatter(ctx.parsed.y)}`;
      chart.update();
      return;
    }

    activityCharts[id] = new Chart(canvas.getContext("2d"), {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Période actuelle",
            data: currentData,
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
            data: previousData,
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
              label: (ctx) => `${ctx.dataset.label}: ${valueFormatter(ctx.parsed.y)}`,
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
            title: { display: true, text: yAxisLabel, color: "#6b7280", font: { size: 11, weight: "600" } },
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

  async function renderCategory(cat, days) {
    const items = activityRaw ? activityRaw[cat.key] || [] : [];
    const stats = computeActivityStats(items, days);
    const rate = (await getRate(cat.sourceCurrency, activityCurrency)) || 1;
    const labels = buildActivityLabels(days);

    const revId = activityCardId(cat, "revenue");
    const curRevenue = stats.currentTotal * rate;
    const prevRevenue = stats.previousTotal * rate;
    setText(`activity-value-${revId}`, formatMoney(curRevenue, activityCurrency));
    setDelta(`activity-delta-${revId}`, curRevenue, prevRevenue);
    renderOrUpdateChart(
      revId,
      labels,
      stats.currentRevenueDaily.map((v) => v * rate),
      stats.previousRevenueDaily.map((v) => v * rate),
      (v) => formatMoney(v, activityCurrency),
      `Revenus générés (${activityCurrency})`
    );

    const countId = activityCardId(cat, "count");
    setText(`activity-value-${countId}`, formatCount(stats.currentCount));
    setDelta(`activity-delta-${countId}`, stats.currentCount, stats.previousCount);
    renderOrUpdateChart(countId, labels, stats.currentCountDaily, stats.previousCountDaily, formatCount, "Nombre");
  }

  async function renderAllActivityCards() {
    if (!activityRaw) return;
    await Promise.all(ACTIVITY_CATEGORIES.map((cat) => renderCategory(cat, activityDays)));
  }

  async function initActivitySection() {
    const grid = document.getElementById("activity-grid");
    if (!grid) return;
    grid.innerHTML = ACTIVITY_CATEGORIES.flatMap((cat) => [activityCardHTML(cat, "revenue"), activityCardHTML(cat, "count")]).join("");

    document.querySelectorAll(".period-btn").forEach((btn) => {
      on(btn, "click", () => {
        document.querySelectorAll(".period-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        activityDays = Number(btn.dataset.period);
        renderAllActivityCards();
      });
    });

    const currencySelect = document.getElementById("activity-currency");
    if (currencySelect) {
      on(currencySelect, "change", () => {
        activityCurrency = currencySelect.value;
        renderAllActivityCards();
      });
    }

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
