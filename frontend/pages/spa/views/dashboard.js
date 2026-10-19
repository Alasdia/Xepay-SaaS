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
            <span id="granularity-selector-label">Hier</span>
            <i class="fa-solid fa-chevron-down"></i>
          </button>
          <div class="hero-popup hero-calendar-popup d-none" id="granularity-popup">
            <div class="hero-calendar-header">
              <button type="button" class="hero-calendar-nav" id="calendar-prev-month"><i class="fa-solid fa-chevron-left"></i></button>
              <span id="calendar-month-label"></span>
              <button type="button" class="hero-calendar-nav" id="calendar-next-month"><i class="fa-solid fa-chevron-right"></i></button>
            </div>
            <div class="hero-calendar-weekdays"><span>L</span><span>M</span><span>M</span><span>J</span><span>V</span><span>S</span><span>D</span></div>
            <div class="hero-calendar-grid" id="calendar-grid"></div>
          </div>
        </div>
      </div>
      <div class="hero-stat-amount-wrap" id="hero-stat-amount-wrap">
        <div class="hero-stat-amount-line">
          <div class="hero-stat-amount" id="hero-stat-amount">—</div>
          <div class="hero-selector" id="hero-currency-selector">
            <button type="button" class="hero-selector-btn hero-chevron-only" id="hero-currency-btn">
              <i class="fa-solid fa-chevron-down"></i>
            </button>
            <div class="hero-popup d-none" id="hero-currency-popup">
              <button type="button" class="hero-popup-item active" data-currency="XOF">XOF</button>
              <button type="button" class="hero-popup-item" data-currency="USD">USD</button>
              <button type="button" class="hero-popup-item" data-currency="EUR">EUR</button>
            </div>
          </div>
        </div>
        <div class="hero-stat-time" id="hero-stat-time"></div>
      </div>
      <div class="hero-chart-wrap" id="hero-chart-wrap">
        <canvas id="hero-chart"></canvas>
        <div class="hero-chart-tooltip" id="hero-chart-tooltip"></div>
      </div>
    </div>
    <div class="hero-balance-side">
      <div class="hero-balance-label">Soldes</div>
      <div class="hero-balance-amount" id="hero-balance-amount">—</div>
      <a href="#" class="hero-balance-link" id="hero-balance-link" title="Voir le solde">Afficher plus <i class="fa-solid fa-arrow-right"></i></a>
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
  let heroMetric = "gross";
  // Devise d'affichage du montant héro et du graphique (sélecteur à côté
  // du montant) — "gross"/"net" sont tirés de nos propres données (liens,
  // wallet), déjà en XOF ; conversion via getRate (mêmes taux fixes que
  // la section "Votre aperçu").
  let heroCurrency = "XOF";
  let heroChart = null;
  // Date comparée à "aujourd'hui" dans le graphique héro, choisie dans le
  // Calendar Popover (par défaut : hier). Jamais aujourd'hui/le futur —
  // désactivés dans le calendrier (comparer "aujourd'hui" à lui-même n'a
  // pas de sens).
  let heroCompareDate = (() => {
    const d = new Date();
    d.setDate(d.getDate() - 1);
    return new Date(d.getFullYear(), d.getMonth(), d.getDate());
  })();
  // Mois affiché dans le calendrier (navigation précédent/suivant),
  // indépendant de heroCompareDate une fois le calendrier ouvert.
  let calendarViewMonth = new Date(heroCompareDate.getFullYear(), heroCompareDate.getMonth(), 1);
  // Dates réelles de chaque bucket du graphique héro (mêmes index que les
  // datasets Chart.js) — lues par le tooltip personnalisé pour afficher la
  // date/heure exacte du point survolé.
  let heroBucketDates = { current: [], previous: [] };

  function startOfDay(date) {
    return new Date(date.getFullYear(), date.getMonth(), date.getDate());
  }

  function formatCompareDateLabel(date) {
    const today = startOfDay(new Date()).getTime();
    const yesterday = today - DAY_MS;
    if (date.getTime() === yesterday) return "Hier";
    if (date.getTime() === today) return "Aujourd'hui";
    return date.toLocaleDateString("fr-FR", { day: "2-digit", month: "short" });
  }

  function sumInRange(items, start, end) {
    return (items || []).reduce((sum, { ts, value }) => (ts != null && ts >= start && ts <= end ? sum + value : sum), 0);
  }

  function countInRange(items, start, end) {
    return (items || []).filter(({ ts }) => ts != null && ts >= start && ts <= end).length;
  }

  // Données brutes derrière chaque métrique héro — mêmes données que la
  // section "Votre aperçu" (aucun appel réseau supplémentaire). "gross" =
  // montant nominal de tous les liens créés (quel que soit leur statut) ;
  // "successful" = liens payés uniquement.
  function heroSourceItems(metric) {
    if (!activityRaw) return [];
    if (metric === "gross") return activityRaw.links || [];
    if (metric === "successful") return (activityRaw.links || []).filter((l) => l.status === "paid");
    if (metric === "net") return activityRaw.balance || [];
    if (metric === "clients") return activityRaw.clients || [];
    if (metric === "products") return activityRaw.products || [];
    return [];
  }

  // Valeur d'une métrique héro sur [start, end] : somme (montants, déjà
  // convertis vers heroCurrency) ou comptage selon l'unité (HERO_METRICS).
  function computeHeroValue(metric, start, end) {
    const items = heroSourceItems(metric);
    if (HERO_METRICS[metric].unit !== "currency") return countInRange(items, start, end);
    return sumInRange(items, start, end) * getRate("XOF", heroCurrency);
  }

  function formatHeroValue(metric, value) {
    return HERO_METRICS[metric].unit === "currency" ? formatMoney(value, heroCurrency) : formatCount(value);
  }

  /* ---------- Graphique héro : buckets, séries, tooltip personnalisé ---------- */

  // 24 buckets horaires pour "aujourd'hui" (current) et pour la date
  // choisie dans le Calendar Popover (previous) — deux jours pas forcément
  // consécutifs, donc calculés indépendamment l'un de l'autre.
  function buildHeroBuckets() {
    const todayBase = startOfDay(new Date());
    const compareBase = startOfDay(heroCompareDate);
    const current = [];
    const previous = [];
    for (let h = 0; h < 24; h++) {
      current.push(new Date(todayBase.getTime() + h * 60 * 60 * 1000));
      previous.push(new Date(compareBase.getTime() + h * 60 * 60 * 1000));
    }
    return { current, previous };
  }

  // Index du dernier bucket dont le départ est <= ts (buckets triés par
  // ordre croissant).
  function findBucketIndex(bucketStartsMs, ts) {
    let idx = -1;
    for (let i = 0; i < bucketStartsMs.length; i++) {
      if (ts >= bucketStartsMs[i]) idx = i;
      else break;
    }
    return idx;
  }

  function computeHeroSeries(metric) {
    const { current, previous } = buildHeroBuckets();
    const curMs = current.map((d) => d.getTime());
    const prevMs = previous.map((d) => d.getTime());
    const currentData = new Array(24).fill(0);
    const previousData = new Array(24).fill(0);
    const now = Date.now();
    const previousEnd = prevMs[0] + DAY_MS;
    const isCount = HERO_METRICS[metric].unit !== "currency";
    const rate = isCount ? 1 : getRate("XOF", heroCurrency);

    heroSourceItems(metric).forEach(({ ts, value }) => {
      if (ts == null) return;
      const amount = isCount ? 1 : value * rate;
      if (ts >= curMs[0] && ts <= now) {
        const idx = findBucketIndex(curMs, ts);
        if (idx !== -1) currentData[idx] += amount;
      }
      if (ts >= prevMs[0] && ts < previousEnd) {
        const idx = findBucketIndex(prevMs, ts);
        if (idx !== -1) previousData[idx] += amount;
      }
    });

    return { current, previous, currentData, previousData };
  }

  // Date + heure exactes du bucket survolé, pour le tooltip.
  function formatHeroBucketDate(date) {
    return (
      date.toLocaleDateString("fr-FR", { weekday: "short", day: "2-digit", month: "short" }) +
      " · " +
      date.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })
    );
  }

  // Date exacte (sans heure) utilisée comme libellé de légende/dataset.
  function formatHeroDayLabel(date) {
    return date.toLocaleDateString("fr-FR", { day: "2-digit", month: "long", year: "numeric" });
  }

  // Trait vertical en pointillés qui suit le point survolé — dessiné à
  // partir des éléments actifs du tooltip Chart.js, donc déjà synchronisé
  // avec le curseur et masqué quand celui-ci quitte le graphique.
  const heroCrosshairPlugin = {
    id: "heroCrosshair",
    afterDatasetsDraw(chart) {
      const active = chart.getActiveElements ? chart.getActiveElements() : [];
      if (!active || !active.length) return;
      const { top, bottom } = chart.chartArea;
      const x = active[0].element.x;
      const ctx = chart.ctx;
      ctx.save();
      ctx.beginPath();
      ctx.setLineDash([4, 4]);
      ctx.lineWidth = 1;
      ctx.strokeStyle = "#9ca3af";
      ctx.moveTo(x, top);
      ctx.lineTo(x, bottom);
      ctx.stroke();
      ctx.restore();
    },
  };

  // Tooltip HTML personnalisé (Chart.js tooltip.external) : date/heure
  // réelle du bucket + valeur période actuelle/précédente en couleurs
  // distinctes, repositionné pour ne jamais sortir du graphique.
  function heroTooltipHandler(context) {
    const { chart, tooltip } = context;
    const el = document.getElementById("hero-chart-tooltip");
    if (!el) return;
    if (!tooltip || tooltip.opacity === 0 || !tooltip.dataPoints || !tooltip.dataPoints.length) {
      el.classList.remove("visible");
      return;
    }

    const idx = tooltip.dataPoints[0].dataIndex;
    const currentDate = heroBucketDates.current[idx];
    const previousDate = heroBucketDates.previous[idx];
    const currentVal = tooltip.dataPoints.find((dp) => dp.datasetIndex === 0)?.parsed.y ?? 0;
    const previousVal = tooltip.dataPoints.find((dp) => dp.datasetIndex === 1)?.parsed.y ?? 0;

    // Dates exactes à la place de "Actuelle"/"Précédente" : chaque ligne
    // porte sa propre date + heure réelle (les 2 jours comparés ne sont
    // pas forcément consécutifs). L'élément comparé (la métrique choisie,
    // ex: "Volume brut") est rappelé en en-tête, séparé des 2 lignes par
    // un trait fin ; les montants sont en gras.
    el.innerHTML = `
      <div class="hero-chart-tooltip-metric">${HERO_METRICS[heroMetric].label}</div>
      <div class="hero-chart-tooltip-divider"></div>
      <div class="hero-chart-tooltip-row current"><span class="hero-chart-tooltip-dot"></span>${currentDate ? formatHeroBucketDate(currentDate) : ""} : <strong class="hero-chart-tooltip-value">${formatHeroValue(heroMetric, currentVal)}</strong></div>
      <div class="hero-chart-tooltip-row previous"><span class="hero-chart-tooltip-dot"></span>${previousDate ? formatHeroBucketDate(previousDate) : ""} : <strong class="hero-chart-tooltip-value">${formatHeroValue(heroMetric, previousVal)}</strong></div>
    `;
    el.classList.add("visible");

    // Repositionnement dans les limites du graphique : à droite du point
    // par défaut, bascule à gauche si ça dépasserait le bord droit ; au-
    // dessus du point, bascule en-dessous si ça dépasserait le bord haut.
    const chartWidth = chart.width;
    const chartHeight = chart.height;
    const tooltipWidth = el.offsetWidth;
    const tooltipHeight = el.offsetHeight;
    let left = tooltip.caretX + 14;
    if (left + tooltipWidth > chartWidth) left = tooltip.caretX - tooltipWidth - 14;
    if (left < 0) left = 4;
    let top = tooltip.caretY - tooltipHeight - 12;
    if (top < 0) top = tooltip.caretY + 12;
    if (top + tooltipHeight > chartHeight) top = chartHeight - tooltipHeight - 4;
    el.style.left = left + "px";
    el.style.top = top + "px";
  }

  function renderHeroChart() {
    const canvas = document.getElementById("hero-chart");
    if (!canvas) return;
    const { current, previous, currentData, previousData } = computeHeroSeries(heroMetric);
    heroBucketDates = { current, previous };
    const labels = current.map((d) => formatHeroBucketDate(d));
    // Dates exactes des 2 jours comparés, utilisées comme libellés de
    // légende à la place de "Période actuelle"/"Période précédente".
    const currentLabel = formatHeroDayLabel(current[0]);
    const previousLabel = formatHeroDayLabel(previous[0]);

    if (heroChart) {
      heroChart.data.labels = labels;
      heroChart.data.datasets[0].data = currentData;
      heroChart.data.datasets[0].label = currentLabel;
      heroChart.data.datasets[1].data = previousData;
      heroChart.data.datasets[1].label = previousLabel;
      heroChart.update();
      return;
    }

    heroChart = new Chart(canvas.getContext("2d"), {
      type: "line",
      plugins: [heroCrosshairPlugin],
      data: {
        labels,
        datasets: [
          {
            label: currentLabel,
            data: currentData,
            borderColor: "#eab308",
            backgroundColor: "rgba(234,179,8,0.1)",
            borderWidth: 2,
            pointRadius: 0,
            pointHoverRadius: 5,
            pointHoverBackgroundColor: "#eab308",
            pointHoverBorderColor: "#ffffff",
            pointHoverBorderWidth: 2,
            tension: 0.3,
            fill: true,
          },
          {
            label: previousLabel,
            data: previousData,
            borderColor: "#9ca3af",
            borderDash: [4, 4],
            borderWidth: 2,
            pointRadius: 0,
            pointHoverRadius: 5,
            pointHoverBackgroundColor: "#9ca3af",
            pointHoverBorderColor: "#ffffff",
            pointHoverBorderWidth: 2,
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
            labels: { boxWidth: 12, boxHeight: 2, color: "#6b7280", font: { size: 13 } },
          },
          tooltip: { enabled: false, external: heroTooltipHandler },
        },
        scales: {
          // Pas de libellés sous l'axe X (dates déjà portées par la
          // légende et le tooltip) — seule la grille/l'axe reste.
          x: { grid: { display: false }, ticks: { display: false } },
          // Pas d'axe Y pour ce graphique : aucune grille, aucun chiffre
          // affiché sur le côté — la valeur ne vit que dans le tooltip, à
          // droite de la date (display:false masque tout l'axe tout en
          // gardant l'échelle pour positionner correctement les courbes).
          y: { display: false, beginAtZero: true, grace: "5%" },
        },
      },
    });

    // Masque le tooltip + le trait vertical dès que le curseur quitte la
    // zone du graphique (évite qu'ils restent affichés "collés").
    on(canvas, "mouseleave", () => {
      document.getElementById("hero-chart-tooltip")?.classList.remove("visible");
      heroChart?.update();
    });
  }

  function renderHeroStat() {
    const todayStart = startOfDay(new Date()).getTime();
    const value = computeHeroValue(heroMetric, todayStart, Date.now());

    setText("metric-selector-label", HERO_METRICS[heroMetric].label);
    setText("granularity-selector-label", formatCompareDateLabel(heroCompareDate));
    setText("hero-stat-amount", formatHeroValue(heroMetric, value));
    setText("hero-stat-time", "Mis à jour à " + new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }));
    setText("hero-balance-amount", formatMoney((activityRaw?.totalBalance || 0) * getRate("XOF", heroCurrency), heroCurrency));

    renderHeroChart();
  }

  function closeHeroPopups() {
    document.getElementById("metric-popup")?.classList.add("d-none");
    document.getElementById("granularity-popup")?.classList.add("d-none");
    document.getElementById("hero-currency-popup")?.classList.add("d-none");
  }

  // Calendar Popover : grille du mois affiché (calendarViewMonth), lundi en
  // première colonne. Aujourd'hui et le futur sont désactivés (comparer
  // "aujourd'hui" à lui-même ou à une date qui n'a pas encore de données
  // n'a pas de sens) ; la date choisie (heroCompareDate) reste surlignée.
  function renderCalendarGrid() {
    const gridEl = document.getElementById("calendar-grid");
    if (!gridEl) return;
    const year = calendarViewMonth.getFullYear();
    const month = calendarViewMonth.getMonth();
    setText("calendar-month-label", calendarViewMonth.toLocaleDateString("fr-FR", { month: "long", year: "numeric" }));

    const firstDay = new Date(year, month, 1);
    const startOffset = (firstDay.getDay() + 6) % 7; // 0 = lundi
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const todayMs = startOfDay(new Date()).getTime();
    const selectedMs = startOfDay(heroCompareDate).getTime();

    let html = "";
    for (let i = 0; i < startOffset; i++) html += `<span class="hero-calendar-cell empty"></span>`;
    for (let d = 1; d <= daysInMonth; d++) {
      const cellMs = new Date(year, month, d).getTime();
      const disabled = cellMs >= todayMs;
      const classes = ["hero-calendar-cell"];
      if (cellMs === todayMs) classes.push("today");
      if (cellMs === selectedMs) classes.push("selected");
      html += `<button type="button" class="${classes.join(" ")}" ${disabled ? "disabled" : ""} data-date="${cellMs}">${d}</button>`;
    }
    gridEl.innerHTML = html;

    gridEl.querySelectorAll(".hero-calendar-cell:not(.empty)").forEach((cell) => {
      on(cell, "click", (e) => {
        e.stopPropagation();
        heroCompareDate = new Date(Number(cell.dataset.date));
        closeHeroPopups();
        renderHeroStat();
      });
    });
  }

  function initHeroStat() {
    on(document.getElementById("hero-currency-btn"), "click", (e) => {
      e.stopPropagation();
      const popup = document.getElementById("hero-currency-popup");
      const wasOpen = !popup.classList.contains("d-none");
      closeHeroPopups();
      popup.classList.toggle("d-none", wasOpen);
    });
    document.querySelectorAll("#hero-currency-popup .hero-popup-item").forEach((btn) => {
      on(btn, "click", () => {
        heroCurrency = btn.dataset.currency;
        document.querySelectorAll("#hero-currency-popup .hero-popup-item").forEach((b) => b.classList.toggle("active", b === btn));
        closeHeroPopups();
        renderHeroStat();
      });
    });
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
      if (wasOpen) return;
      calendarViewMonth = new Date(heroCompareDate.getFullYear(), heroCompareDate.getMonth(), 1);
      renderCalendarGrid();
      popup.classList.remove("d-none");
    });
    document.querySelectorAll("#metric-popup .hero-popup-item").forEach((btn) => {
      on(btn, "click", () => {
        heroMetric = btn.dataset.metric;
        document.querySelectorAll("#metric-popup .hero-popup-item").forEach((b) => b.classList.toggle("active", b === btn));
        closeHeroPopups();
        renderHeroStat();
      });
    });
    on(document.getElementById("calendar-prev-month"), "click", (e) => {
      e.stopPropagation();
      calendarViewMonth = new Date(calendarViewMonth.getFullYear(), calendarViewMonth.getMonth() - 1, 1);
      renderCalendarGrid();
    });
    on(document.getElementById("calendar-next-month"), "click", (e) => {
      e.stopPropagation();
      calendarViewMonth = new Date(calendarViewMonth.getFullYear(), calendarViewMonth.getMonth() + 1, 1);
      renderCalendarGrid();
    });
    on(document, "click", closeHeroPopups);

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
      heroChart?.destroy();
      boundListeners.forEach(({ target, type, fn }) => target.removeEventListener(type, fn));
    },
  };
}
