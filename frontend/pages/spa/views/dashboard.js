// Vue "Dashboard" (accueil) — en haut, un bloc "héro" (titre de période +
// sélecteur d'activité/de granularité + montant, et à droite le solde avec
// lien vers la vue Solde) ; en dessous, la section "Votre aperçu" : pour
// chaque catégorie (clients, produits, factures, abonnements, liens),
// deux blocs côte à côte — un pour les revenus générés, un pour le nombre
// d'éléments — chacun avec sa propre courbe (période actuelle vs
// précédente), alignés 2 par 2. Les revenus sont affichés dans la devise
// choisie (USD par défaut), convertis via les mêmes taux fixes que le
// reste de l'app (voir FIXED_RATES_TO_XOF) plutôt qu'un taux de marché en
// direct.
import { apiFetch } from "../core/apiClient.js";
import { setViewStyles } from "../core/styleLoader.js";
import { navigate } from "../core/router.js";
import { getWorkspaceId } from "../core/state.js";

const TEMPLATE = `
<div class="hero-stat mb-4" id="hero-stat">
  <div class="hero-stat-title" id="hero-stat-title">Aujourd'hui</div>
  <div class="hero-stat-divider"></div>
  <div class="hero-stat-row">
    <div class="hero-stat-main">
      <div class="hero-stat-selectors">
        <div class="hero-selector" id="metric-selector">
          <button type="button" class="hero-selector-btn" id="metric-selector-btn">
            <span id="metric-selector-label">Volume brut</span>
            <i class="fa-solid fa-chevron-down"></i>
          </button>
          <div class="hero-popup d-none" id="metric-popup">
            <button type="button" class="hero-popup-item active" data-metric="gross">Volume brut</button>
            <button type="button" class="hero-popup-item" data-metric="successful">Paiements réussis</button>
            <button type="button" class="hero-popup-item" data-metric="net">Volume net</button>
            <button type="button" class="hero-popup-item" data-metric="clients">Nouveaux clients</button>
            <button type="button" class="hero-popup-item" data-metric="products">Nouveaux produits</button>
          </div>
        </div>
        <div class="hero-selector" id="granularity-selector">
          <button type="button" class="hero-selector-btn" id="granularity-selector-btn">
            <span id="granularity-selector-label">Jour</span>
            <i class="fa-solid fa-chevron-down"></i>
          </button>
          <div class="hero-popup d-none" id="granularity-popup">
            <button type="button" class="hero-popup-item active" data-granularity="day">Jour</button>
            <button type="button" class="hero-popup-item" data-granularity="month">Mois</button>
            <button type="button" class="hero-popup-item" data-granularity="year">Année</button>
          </div>
        </div>
      </div>
      <div class="hero-stat-amount-wrap" id="hero-stat-amount-wrap">
        <div class="hero-stat-amount" id="hero-stat-amount">—</div>
        <div class="hero-stat-time" id="hero-stat-time"></div>
        <div class="hero-stat-hovercard d-none" id="hero-stat-hovercard"></div>
      </div>
    </div>
    <div class="hero-balance-side">
      <div class="hero-balance-label">Soldes</div>
      <div class="hero-balance-amount" id="hero-balance-amount">—</div>
      <a href="#" class="hero-balance-link" id="hero-balance-link" title="Voir le solde"><i class="fa-solid fa-arrow-right"></i></a>
    </div>
  </div>
</div>
<div class="activity-section mb-4">
  <div class="activity-section-head">
    <h5 class="fw-bold mb-0 text-muted">Votre aperçu</h5>
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
    { key: "invoices", label: "Factures", icon: "fa-file-invoice", sourceCurrency: "USD" },
    { key: "subscriptions", label: "Abonnements", icon: "fa-rotate", sourceCurrency: "USD" },
    { key: "links", label: "Liens de paiement", icon: "fa-link", sourceCurrency: "XOF" },
  ];

  let activityRaw = null;
  let activityDays = 30;
  let activityCurrency = "USD";
  const activityCharts = {};

  // Taux fixes vers XOF, alignés sur ceux déjà utilisés ailleurs dans
  // l'app (ex: USD_RATE dans backend/routes/payout.py) plutôt qu'un taux
  // de marché en direct. EUR/XOF = parité officielle UEMOA/CEMAC.
  const FIXED_RATES_TO_XOF = { XOF: 1, USD: 577.325, EUR: 655.957 };

  function getRate(from, to) {
    if (from === to) return 1;
    const fromToXof = FIXED_RATES_TO_XOF[from];
    const toToXof = FIXED_RATES_TO_XOF[to];
    if (!fromToXof || !toToXof) return 1;
    return fromToXof / toToXof;
  }

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

  // Tous les liens sont désormais créés depuis la vue Liens (le flux de
  // création du dashboard a été retiré) : /links reflète donc déjà
  // l'ensemble des liens créés par le marchand. L'endpoint est paginé
  // (limit/offset, pas de filtre de date) : on parcourt les pages jusqu'à
  // dépasser la fenêtre la plus large utile (90 jours actuels + 90 jours
  // précédents) plutôt que de se limiter à une seule page qui pourrait
  // couper des liens pertinents si le marchand en a créé beaucoup.
  const MAX_ACTIVITY_PERIOD_DAYS = 90;
  const LINKS_PAGE_SIZE = 200;

  async function fetchAllLinks() {
    const cutoff = Date.now() - 2 * MAX_ACTIVITY_PERIOD_DAYS * DAY_MS;
    const all = [];
    let offset = 0;
    while (true) {
      let res;
      try {
        res = await apiFetch(`/links?limit=${LINKS_PAGE_SIZE}&offset=${offset}`);
      } catch {
        break;
      }
      if (!res.ok) break;
      let page;
      try {
        page = await res.json();
      } catch {
        break;
      }
      if (!Array.isArray(page) || page.length === 0) break;
      all.push(...page);
      const oldestTs = toTimestamp(page[page.length - 1].created_at);
      if (page.length < LINKS_PAGE_SIZE || (oldestTs != null && oldestTs < cutoff)) break;
      offset += LINKS_PAGE_SIZE;
    }
    return all;
  }

  async function fetchActivityRawData() {
    const [settled, linksData] = await Promise.all([
      Promise.allSettled([
        apiFetch("/stripe/connect/customers"),
        apiFetch("/stripe/connect/products"),
        apiFetch("/stripe/connect/subscriptions"),
        apiFetch("/stripe/connect/invoices"),
        apiFetch("/wallet/history?limit=300"),
        apiFetch("/wallet/me"),
      ]),
      fetchAllLinks().catch(() => []),
    ]);
    const [customersRes, productsRes, subscriptionsRes, invoicesRes, walletRes, walletMeRes] = settled;

    const customersData = await safeJson(customersRes);
    const productsData = await safeJson(productsRes);
    const subscriptionsData = await safeJson(subscriptionsRes);
    const invoicesData = await safeJson(invoicesRes);
    const walletData = await safeJson(walletRes);
    const walletMeData = await safeJson(walletMeRes);

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
      // status conservé ici (utilisé uniquement par le bloc "Nombre" des
      // liens, pour les distinguer payé/en attente/expiré).
      links: (Array.isArray(linksData) ? linksData : []).map((l) => ({
        ts: toTimestamp(l.created_at),
        value: l.amount || 0,
        status: l.status,
      })),
      balance: (walletData?.transactions || []).map((t) => ({
        ts: toTimestamp(t.created_at),
        value: t.direction === "out" ? -Math.abs(t.amount) : Math.abs(t.amount),
      })),
      totalBalance: Number(walletMeData?.available || 0),
    };
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

  // Datasets standard "période actuelle vs précédente", utilisés par tous
  // les blocs sauf le nombre de liens (voir buildLinksStatusDatasets).
  function buildComparisonDatasets(currentData, previousData) {
    return [
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
    ];
  }

  // Bloc "Liens de paiement — Nombre" uniquement : au lieu de comparer la
  // période actuelle à la précédente, distingue les liens créés dans la
  // période par statut (payé/en attente/expiré) — un mécanisme différent,
  // propre à ce bloc, demandé explicitement pour ne pas tout mélanger dans
  // un seul "nombre de liens".
  // pointRadius > 0 ici (contrairement aux autres graphiques) : une
  // courbe "En attente"/"Expirés" à 0 toute la période est une ligne
  // plate collée à l'axe — sans point visible, elle se confond avec l'axe
  // et paraît absente. Les points, eux, restent visibles même à 0.
  function buildLinksStatusDatasets(daily) {
    return [
      { label: "Payés", data: daily.paid, borderColor: "#16a34a", backgroundColor: "#16a34a", borderWidth: 2, pointRadius: 3, pointHoverRadius: 5, tension: 0.3, fill: false },
      { label: "En attente", data: daily.pending, borderColor: "#eab308", backgroundColor: "#eab308", borderWidth: 2, pointRadius: 3, pointHoverRadius: 5, tension: 0.3, fill: false },
      { label: "Expirés", data: daily.expired, borderColor: "#dc2626", backgroundColor: "#dc2626", borderWidth: 2, pointRadius: 3, pointHoverRadius: 5, tension: 0.3, fill: false },
    ];
  }

  function renderOrUpdateChart(id, labels, datasets, valueFormatter, yAxisLabel) {
    const canvas = document.getElementById(`activity-chart-${id}`);
    if (!canvas) return;

    if (activityCharts[id]) {
      const chart = activityCharts[id];
      chart.data.labels = labels;
      chart.data.datasets = datasets;
      chart.options.scales.y.title.text = yAxisLabel;
      chart.options.plugins.tooltip.callbacks.label = (ctx) => `${ctx.dataset.label}: ${valueFormatter(ctx.parsed.y)}`;
      chart.update();
      return;
    }

    activityCharts[id] = new Chart(canvas.getContext("2d"), {
      type: "line",
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: {
            position: "top",
            align: "end",
            labels: { boxWidth: 12, boxHeight: 2, color: "#6b7280", font: { size: 13 } },
          },
          tooltip: {
            titleFont: { size: 13 },
            bodyFont: { size: 13 },
            callbacks: {
              label: (ctx) => `${ctx.dataset.label}: ${valueFormatter(ctx.parsed.y)}`,
            },
          },
        },
        scales: {
          x: {
            title: { display: true, text: "Période (jour)", color: "#6b7280", font: { size: 13, weight: "600" } },
            grid: { display: false },
            ticks: { color: "#9ca3af", font: { size: 13 }, maxRotation: 0, autoSkip: true },
          },
          y: {
            title: { display: true, text: yAxisLabel, color: "#6b7280", font: { size: 13, weight: "600" } },
            beginAtZero: true,
            // grace : marge au-dessus/en-dessous des données même à 0, pour
            // qu'une courbe plate à 0 ne colle pas pile sur l'axe (sinon
            // elle se confond avec le trait de l'axe et paraît invisible).
            grace: "5%",
            grid: { color: "#e5e7eb" },
            ticks: {
              color: "#9ca3af",
              font: { size: 13 },
              callback: (val) => Number(val).toLocaleString("fr-FR"),
            },
          },
        },
      },
    });
  }

  // Nombre de liens par statut (payé/en attente/expiré), jour par jour,
  // sur la période actuelle uniquement — voir buildLinksStatusDatasets.
  function computeLinksStatusDaily(items, days) {
    const now = Date.now();
    const currentStart = now - days * DAY_MS;
    const daily = { paid: new Array(days).fill(0), pending: new Array(days).fill(0), expired: new Array(days).fill(0) };

    items.forEach(({ ts, status }) => {
      if (ts == null || ts < currentStart || ts > now || !daily[status]) return;
      const idx = Math.min(days - 1, Math.max(0, Math.floor((ts - currentStart) / DAY_MS)));
      daily[status][idx] += 1;
    });

    return daily;
  }

  async function renderCategory(cat, days) {
    const items = activityRaw ? activityRaw[cat.key] || [] : [];
    const stats = computeActivityStats(items, days);
    const rate = getRate(cat.sourceCurrency, activityCurrency) || 1;
    const labels = buildActivityLabels(days);

    const revId = activityCardId(cat, "revenue");
    const curRevenue = stats.currentTotal * rate;
    const prevRevenue = stats.previousTotal * rate;
    setText(`activity-value-${revId}`, formatMoney(curRevenue, activityCurrency));
    setDelta(`activity-delta-${revId}`, curRevenue, prevRevenue);
    renderOrUpdateChart(
      revId,
      labels,
      buildComparisonDatasets(
        stats.currentRevenueDaily.map((v) => v * rate),
        stats.previousRevenueDaily.map((v) => v * rate)
      ),
      (v) => formatMoney(v, activityCurrency),
      `Revenus générés (${activityCurrency})`
    );

    const countId = activityCardId(cat, "count");
    setText(`activity-value-${countId}`, formatCount(stats.currentCount));
    setDelta(`activity-delta-${countId}`, stats.currentCount, stats.previousCount);
    if (cat.key === "links") {
      renderOrUpdateChart(countId, labels, buildLinksStatusDatasets(computeLinksStatusDaily(items, days)), formatCount, "Nombre (par statut)");
    } else {
      renderOrUpdateChart(countId, labels, buildComparisonDatasets(stats.currentCountDaily, stats.previousCountDaily), formatCount, "Nombre");
    }
  }

  async function renderAllActivityCards() {
    if (!activityRaw) return;
    await Promise.all(ACTIVITY_CATEGORIES.map((cat) => renderCategory(cat, activityDays)));
  }

  /* =====================================================
     BLOC "HÉRO" — titre de granularité, 2 sélecteurs (activité, période
     jour/mois/année), montant + heure, et le solde total à droite (lien
     vers la vue Solde). Indépendant de la devise/période de la section
     "Votre aperçu" plus bas.
  ===================================================== */

  const HERO_METRICS = {
    gross: { label: "Volume brut", unit: "currency" },
    successful: { label: "Paiements réussis", unit: "count" },
    net: { label: "Volume net", unit: "currency" },
    clients: { label: "Nouveaux clients", unit: "count" },
    products: { label: "Nouveaux produits", unit: "count" },
  };
  const HERO_GRANULARITIES = {
    day: { label: "Jour", title: "Aujourd'hui" },
    month: { label: "Mois", title: "Ce mois-ci" },
    year: { label: "Année", title: "Cette année" },
  };

  let heroMetric = "gross";
  let heroGranularity = "day";

  // Bornes (start inclus, end exclu) du jour calendaire "aujourd'hui moins
  // offsetDays" (0 = aujourd'hui, 1 = hier), en heure locale.
  function getDayBounds(offsetDays) {
    const now = new Date();
    const start = new Date(now.getFullYear(), now.getMonth(), now.getDate() - offsetDays, 0, 0, 0, 0).getTime();
    return { start, end: start + DAY_MS };
  }

  // Bornes du jour/mois/année calendaire en cours (start inclus, "now" en
  // borne haute).
  function getGranularityBounds(granularity) {
    const now = new Date();
    let start;
    if (granularity === "month") start = new Date(now.getFullYear(), now.getMonth(), 1);
    else if (granularity === "year") start = new Date(now.getFullYear(), 0, 1);
    else start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    return { start: start.getTime(), end: Date.now() };
  }

  function sumInRange(items, start, end) {
    return (items || []).reduce((sum, { ts, value }) => (ts != null && ts >= start && ts <= end ? sum + value : sum), 0);
  }

  function countInRange(items, start, end) {
    return (items || []).filter(({ ts }) => ts != null && ts >= start && ts <= end).length;
  }

  // Valeur d'une métrique héro sur [start, end] — réutilise les mêmes
  // données brutes que la section "Votre aperçu" (aucun appel réseau
  // supplémentaire). "gross" = montant nominal de tous les liens créés
  // (quel que soit leur statut) ; "successful" = nombre de liens payés.
  function computeHeroValue(metric, start, end) {
    if (!activityRaw) return 0;
    if (metric === "gross") return sumInRange(activityRaw.links, start, end);
    if (metric === "successful") return countInRange((activityRaw.links || []).filter((l) => l.status === "paid"), start, end);
    if (metric === "net") return sumInRange(activityRaw.balance, start, end);
    if (metric === "clients") return countInRange(activityRaw.clients, start, end);
    if (metric === "products") return countInRange(activityRaw.products, start, end);
    return 0;
  }

  function formatHeroValue(metric, value) {
    return HERO_METRICS[metric].unit === "currency" ? formatMoney(value, "XOF") : formatCount(value);
  }

  function renderHeroStat() {
    const { start, end } = getGranularityBounds(heroGranularity);
    const value = computeHeroValue(heroMetric, start, end);

    setText("hero-stat-title", HERO_GRANULARITIES[heroGranularity].title);
    setText("metric-selector-label", HERO_METRICS[heroMetric].label);
    setText("granularity-selector-label", HERO_GRANULARITIES[heroGranularity].label);
    setText("hero-stat-amount", formatHeroValue(heroMetric, value));
    setText("hero-stat-time", "Mis à jour à " + new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }));
    setText("hero-balance-amount", Math.round(activityRaw?.totalBalance || 0).toLocaleString("fr-FR") + " XOF");

    // Toujours "aujourd'hui", peu importe la granularité choisie au-dessus
    // — sert de repère rapide au survol, comme les tooltips des graphiques.
    const todayBounds = getDayBounds(0);
    const todayValue = computeHeroValue(heroMetric, todayBounds.start, todayBounds.end);
    const hovercard = document.getElementById("hero-stat-hovercard");
    if (hovercard) hovercard.textContent = `Aujourd'hui : ${formatHeroValue(heroMetric, todayValue)}`;
  }

  function closeHeroPopups() {
    document.getElementById("metric-popup")?.classList.add("d-none");
    document.getElementById("granularity-popup")?.classList.add("d-none");
  }

  function initHeroStat() {
    on(document.getElementById("metric-selector-btn"), "click", (e) => {
      e.stopPropagation();
      const popup = document.getElementById("metric-popup");
      const wasOpen = !popup.classList.contains("d-none");
      closeHeroPopups();
      popup.classList.toggle("d-none", wasOpen);
    });
    on(document.getElementById("granularity-selector-btn"), "click", (e) => {
      e.stopPropagation();
      const popup = document.getElementById("granularity-popup");
      const wasOpen = !popup.classList.contains("d-none");
      closeHeroPopups();
      popup.classList.toggle("d-none", wasOpen);
    });
    document.querySelectorAll("#metric-popup .hero-popup-item").forEach((btn) => {
      on(btn, "click", () => {
        heroMetric = btn.dataset.metric;
        document.querySelectorAll("#metric-popup .hero-popup-item").forEach((b) => b.classList.toggle("active", b === btn));
        closeHeroPopups();
        renderHeroStat();
      });
    });
    document.querySelectorAll("#granularity-popup .hero-popup-item").forEach((btn) => {
      on(btn, "click", () => {
        heroGranularity = btn.dataset.granularity;
        document.querySelectorAll("#granularity-popup .hero-popup-item").forEach((b) => b.classList.toggle("active", b === btn));
        closeHeroPopups();
        renderHeroStat();
      });
    });
    on(document, "click", closeHeroPopups);

    const amountWrap = document.getElementById("hero-stat-amount-wrap");
    const hovercard = document.getElementById("hero-stat-hovercard");
    if (amountWrap && hovercard) {
      on(amountWrap, "mouseenter", () => hovercard.classList.remove("d-none"));
      on(amountWrap, "mouseleave", () => hovercard.classList.add("d-none"));
    }

    on(document.getElementById("hero-balance-link"), "click", (e) => {
      e.preventDefault();
      navigate(`/dash/workspace/${getWorkspaceId() || "me"}/solde`);
    });
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

    initHeroStat();

    activityRaw = await fetchActivityRawData();
    renderHeroStat();
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
