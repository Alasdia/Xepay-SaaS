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
          <div class="hero-granularity-amount" id="granularity-selector-amount">—</div>
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
    <h5 class="activity-section-title fw-bold mb-0 text-muted">Votre aperçu</h5>
    <div class="activity-filters">
    <div class="activity-filters-left">
      <div class="activity-filter" id="activity-currency-filter">
        <button type="button" class="activity-filter-btn" id="activity-currency-btn">
          <span class="activity-filter-label">Devise</span>
          <span class="activity-filter-value" id="activity-currency-label">USD</span>
          <i class="fa-solid fa-chevron-down"></i>
        </button>
        <div class="activity-filter-popup d-none" id="activity-currency-popup">
          <button type="button" class="activity-filter-item active" data-currency="USD">USD</button>
          <button type="button" class="activity-filter-item" data-currency="EUR">EUR</button>
          <button type="button" class="activity-filter-item" data-currency="XOF">XOF</button>
        </div>
      </div>
      <div class="activity-filter" id="activity-period-filter">
        <button type="button" class="activity-filter-btn" id="activity-period-btn">
          <span class="activity-filter-label">Période précédente</span>
          <span class="activity-filter-value" id="activity-period-label">Mois</span>
          <i class="fa-solid fa-chevron-down"></i>
        </button>
        <div class="activity-filter-popup d-none" id="activity-period-popup">
          <button type="button" class="activity-filter-item" data-period="hour">Jour</button>
          <button type="button" class="activity-filter-item" data-period="week">Semaine</button>
          <button type="button" class="activity-filter-item active" data-period="month">Mois</button>
          <button type="button" class="activity-filter-item" data-period="year">Année</button>
        </div>
      </div>
      <div class="activity-filter" id="activity-net-filter">
        <button type="button" class="activity-filter-btn" id="activity-net-btn">
          <span class="activity-filter-label">Revenus</span>
          <span class="activity-filter-value" id="activity-net-label">Revenu brut</span>
          <i class="fa-solid fa-chevron-down"></i>
        </button>
        <div class="activity-filter-popup d-none" id="activity-net-popup">
          <button type="button" class="activity-filter-item active" data-net="gross">Revenu brut</button>
          <button type="button" class="activity-filter-item" data-net="net">Revenu net</button>
        </div>
      </div>
    </div>
      <div class="activity-block-actions">
        <div class="activity-filter" id="activity-add-filter">
          <button type="button" class="activity-filter-btn" id="activity-add-btn">
            <i class="fa-solid fa-plus"></i>
            <span>Ajouter</span>
          </button>
          <div class="activity-filter-popup d-none" id="activity-add-popup"></div>
        </div>
        <button type="button" class="activity-filter-btn" id="activity-edit-btn">
          <span id="activity-edit-label">Modifier</span>
        </button>
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
     SECTION "ACTIVITÉ" — 5 catégories × 2 blocs (revenus, nombre),
     comparant la période choisie (7/30/90 jours) à la période
     équivalente précédente. Chaque bloc "Revenus" ne compte que l'argent
     réellement encaissé (filtré par statut) et convertit chaque élément
     depuis sa propre devise Stripe/lien (jamais un taux fixe par
     catégorie) — voir renderCategory.
  ===================================================== */

  const DAY_MS = 24 * 60 * 60 * 1000;
  const HOUR_MS = 60 * 60 * 1000;

  const ACTIVITY_CATEGORIES = [
    { key: "clients", label: "Nouveaux clients", icon: "fa-user-plus" },
    { key: "products", label: "Nouveaux produits", icon: "fa-box" },
    { key: "invoices", label: "Factures", icon: "fa-file-invoice" },
    { key: "subscriptions", label: "Abonnements", icon: "fa-rotate" },
    { key: "links", label: "Liens de paiement", icon: "fa-link" },
  ];

  // Les 10 blocs par défaut (revenus+nombre × 5 catégories), déjà visibles
  // à l'ouverture de la vue — "retirables" comme n'importe quel bloc via le
  // bouton Modifier.
  const DEFAULT_BLOCKS = ACTIVITY_CATEGORIES.flatMap((cat) => [
    { id: `${cat.key}-revenue`, row: cat.key, label: `${cat.label} — Revenus` },
    { id: `${cat.key}-count`, row: cat.key, label: `${cat.label} — Nombre` },
  ]);
  const DEFAULT_BLOCK_IDS = DEFAULT_BLOCKS.map((b) => b.id);

  // Blocs optionnels proposés via "+ Ajouter" — masqués par défaut. "row"
  // détermine dans quelle ligne (même grille que les blocs par défaut de
  // cette catégorie) le bloc rejoint, avec adaptation automatique de la
  // largeur des colonnes (voir .activity-row, grid-template-columns en
  // auto-fit : passe de 2 à 3 colonnes sans JS de mise en page).
  const BLOCK_CATALOG = [
    { id: "clients-top", row: "clients", label: "Meilleur client (montant dépensé)", icon: "fa-trophy", kind: "topEntity" },
    { id: "products-top", row: "products", label: "Meilleur produit (revenu généré)", icon: "fa-trophy", kind: "topEntity" },
    { id: "invoices-refunds", row: "invoices", label: "Remboursements (factures)", icon: "fa-rotate-left", kind: "metric" },
    { id: "subscriptions-refunds", row: "subscriptions", label: "Remboursements (abonnements)", icon: "fa-rotate-left", kind: "metric" },
    { id: "links-refunds", row: "links", label: "Remboursements (liens de paiement)", icon: "fa-rotate-left", kind: "metric" },
  ];

  const ACTIVITY_BLOCKS_STORAGE_KEY = "xepay_activity_blocks_v1";

  function loadVisibleBlocks() {
    try {
      const raw = localStorage.getItem(ACTIVITY_BLOCKS_STORAGE_KEY);
      if (raw) return new Set(JSON.parse(raw));
    } catch {
      // localStorage indisponible (navigation privée, etc.) : repli sur les
      // blocs par défaut, sans persistance.
    }
    return new Set(DEFAULT_BLOCK_IDS);
  }

  function saveVisibleBlocks() {
    try {
      localStorage.setItem(ACTIVITY_BLOCKS_STORAGE_KEY, JSON.stringify([...visibleActivityBlocks]));
    } catch {
      // Pas grave : la personnalisation ne survivra juste pas au rechargement.
    }
  }

  let visibleActivityBlocks = loadVisibleBlocks();
  let activityEditMode = false;

  // Chaque option = un nombre de "buckets" (count) de taille bucketMs : les
  // fonctions de calcul (computeActivityStats, etc.) sont génériques sur
  // cette taille, donc "Jour" (buckets horaires) réutilise exactement la
  // même logique que "Semaine"/"Mois"/"Année" (buckets journaliers).
  const ACTIVITY_PERIODS = {
    hour: { label: "Jour", count: 24, bucketMs: HOUR_MS },
    week: { label: "Semaine", count: 7, bucketMs: DAY_MS },
    month: { label: "Mois", count: 30, bucketMs: DAY_MS },
    year: { label: "Année", count: 365, bucketMs: DAY_MS },
  };

  let activityRaw = null;
  let activityPeriodKey = "month";
  let activityCurrency = "USD";
  let activityNetMode = "gross";

  function currentActivityPeriod() {
    return ACTIVITY_PERIODS[activityPeriodKey];
  }
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

  // Coquille commune à tous les blocs (par défaut ou catalogue) : icône +
  // titre, le bouton de retrait (visible seulement en mode édition, voir
  // toggleActivityEditMode) et un corps qui varie selon le type de bloc.
  function activityCardShellHTML(id, icon, title, bodyHtml) {
    return `
      <div class="activity-card" data-key="${id}">
        <button type="button" class="activity-card-remove d-none" data-remove="${id}" title="Retirer ce bloc"><i class="fa-solid fa-xmark"></i></button>
        <div class="activity-card-head">
          <span class="activity-card-icon"><i class="fa-solid ${icon}"></i></span>
          <span class="activity-card-title">${title}</span>
        </div>
        ${bodyHtml}
      </div>
    `;
  }

  // Corps "métrique + graphe comparatif" : tous les blocs par défaut
  // (revenus/nombre) et les remboursements du catalogue.
  function metricCardBodyHTML(id) {
    return `
      <div class="activity-card-metric">
        <span class="activity-value" id="activity-value-${id}">—</span>
        <span class="activity-delta" id="activity-delta-${id}"></span>
      </div>
      <div class="activity-chart-wrap">
        <canvas id="activity-chart-${id}"></canvas>
        <div class="hero-chart-tooltip" id="activity-chart-tooltip-${id}"></div>
      </div>
    `;
  }

  // Corps "classement" (pas de graphe, pas de comparaison) : Meilleur
  // client/produit — voir computeTopEntity.
  function topEntityCardBodyHTML(id) {
    return `
      <div class="activity-top-entity">
        <div class="activity-top-entity-name" id="activity-top-name-${id}">—</div>
        <div class="activity-top-entity-amount" id="activity-top-amount-${id}">—</div>
      </div>
    `;
  }

  function activityCardHTML(cat, kind) {
    const id = activityCardId(cat, kind);
    const title = kind === "revenue" ? `${cat.label} — Revenus` : `${cat.label} — Nombre`;
    return activityCardShellHTML(id, cat.icon, title, metricCardBodyHTML(id));
  }

  // Une ligne (.activity-row) par catégorie, contenant uniquement les blocs
  // actuellement visibles (visibleActivityBlocks) : par défaut (revenus/
  // nombre) puis, dans l'ordre du catalogue, ceux qui ont été ajoutés pour
  // cette catégorie. grid-template-columns en auto-fit (voir CSS) adapte
  // automatiquement le nombre de colonnes de 2 à 3 sans calcul en JS.
  function buildActivityGridHTML() {
    return ACTIVITY_CATEGORIES.map((cat) => {
      const cards = [];
      if (visibleActivityBlocks.has(activityCardId(cat, "revenue"))) cards.push(activityCardHTML(cat, "revenue"));
      if (visibleActivityBlocks.has(activityCardId(cat, "count"))) cards.push(activityCardHTML(cat, "count"));
      BLOCK_CATALOG.filter((b) => b.row === cat.key && visibleActivityBlocks.has(b.id)).forEach((b) => {
        const body = b.kind === "topEntity" ? topEntityCardBodyHTML(b.id) : metricCardBodyHTML(b.id);
        cards.push(activityCardShellHTML(b.id, b.icon, b.label, body));
      });
      if (!cards.length) return "";
      return `<div class="activity-row">${cards.join("")}</div>`;
    }).join("");
  }

  // Unix (secondes, objets Stripe) ou ISO (nos propres endpoints) -> ms.
  function toTimestamp(raw) {
    if (raw == null) return null;
    if (typeof raw === "number") return raw * 1000;
    const t = new Date(raw).getTime();
    return Number.isNaN(t) ? null : t;
  }

  // Même logique que backend/routes/webhook/stripe.py (process_invoice_paid_event) :
  // depuis l'API Stripe 2025-03-31.basil, invoice.subscription est retiré au
  // profit de invoice.parent.subscription_details.subscription. Lire
  // l'ancien champ seul classe silencieusement TOUTE facture d'abonnement
  // comme facture "one-off" (jamais "abonnement") sur cette version d'API —
  // l'ancien champ est gardé en repli au cas où l'API version du compte
  // changerait.
  function extractInvoiceSubscriptionId(invoice) {
    const parent = invoice.parent || {};
    if (parent.type === "subscription_details") {
      return parent.subscription_details?.subscription || null;
    }
    return invoice.subscription || null;
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
  // dépasser la fenêtre la plus large utile (365 jours actuels + 365 jours
  // précédents, "Année précédente" étant la plus longue période
  // sélectionnable) plutôt que de se limiter à une seule page qui pourrait
  // couper des liens pertinents si le marchand en a créé beaucoup.
  const MAX_ACTIVITY_PERIOD_DAYS = 365;
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

    // "value" = montant brut de l'élément, dans sa propre devise (jamais un
    // simple comptage, qui est dérivé séparément à l'affichage) : montant de
    // l'abonnement/de la facture/du lien. Stripe renvoie ses montants en
    // centimes (voir le même /100 partout dans commerce.js) ; nos propres
    // endpoints (liens, wallet) sont déjà en unité pleine.
    // "clients"/"products" n'ont pas de "value" propre : leur revenu ne
    // vient pas d'un champ Stripe de l'entité elle-même mais des factures
    // payées rattachées via customerId/productId (voir
    // computeEntityCohortRevenue plus bas), croisées au rendu.
    //
    // Depuis l'API Stripe 2025-03-31.basil, une ligne de facture n'a plus de
    // champ "price" (objet, avec .product) : il faut lire
    // line.pricing.price_details.price (un ID de Price, pas un objet) après
    // avoir vérifié pricing.type === "price_details", puis retrouver le
    // produit correspondant soi-même — Stripe ne renvoie plus cette relation
    // "gratuitement" sur la ligne. On construit cette correspondance ici
    // depuis /stripe/connect/products, qui renvoie déjà chaque Price complet
    // (avec son id) sous product.prices.
    const priceToProduct = new Map();
    (productsData?.data || []).forEach((p) => {
      (p.prices || []).forEach((price) => {
        if (price?.id) priceToProduct.set(price.id, p.id);
      });
    });
    function extractLineProductId(line) {
      if (!line) return null;
      let priceId = null;
      if (line.pricing?.type === "price_details") {
        priceId = line.pricing.price_details?.price || null;
      } else if (line.price) {
        // Repli pour une version d'API antérieure à basil, où price était
        // encore un objet expandable portant directement .product.
        priceId = typeof line.price === "string" ? line.price : line.price.id || null;
        if (line.price?.product) return line.price.product;
      }
      return priceId ? priceToProduct.get(priceId) || null : null;
    }

    return {
      // name : utilisé par le bloc "Meilleur client" (voir computeTopEntity).
      clients: (customersData?.data || []).map((c) => ({ id: c.id, ts: toTimestamp(c.created), name: c.name || c.email || "Client" })),
      // id seul (pas de "value") : comme pour les clients, le revenu d'un
      // produit ne vient pas d'un champ Stripe du produit lui-même (son prix
      // catalogue existe dès sa création, qu'il soit vendu ou non) mais des
      // factures/abonnements qui le référencent — voir computeProductRevenue.
      // name : utilisé par le bloc "Meilleur produit".
      products: (productsData?.data || []).map((p) => ({ id: p.id, ts: toTimestamp(p.created), name: p.name || "Produit" })),
      // status + currency conservés ici aussi : utilisés par le bloc héro
      // pour ne garder que les abonnements actifs (paiement effectif) et
      // convertir depuis leur vraie devise (Stripe, pas forcément XOF).
      // customerId/productId : utilisés par computeEntityCohortRevenue pour
      // rattacher ce paiement au client et au produit Stripe concernés.
      subscriptions: (subscriptionsData?.data || []).map((s) => {
        const item = s.items?.data?.[0];
        const unitAmount = item?.price?.unit_amount || 0;
        const quantity = item?.quantity || 1;
        return {
          ts: toTimestamp(s.created),
          value: (unitAmount * quantity) / 100,
          status: s.status,
          currency: (item?.price?.currency || "usd").toUpperCase(),
          customerId: s.customer || null,
          productId: item?.price?.product || null,
        };
      }),
      // status + currency : le bloc héro ne garde que les factures payées
      // ("paid"), converties depuis leur vraie devise. customerId/productId :
      // idem abonnements, pour le rattachement au bon client/produit. On ne
      // regarde que la première ligne (comme pour les abonnements) : avec
      // seulement 2 produits dans ce compte, les factures n'ont en pratique
      // qu'une seule ligne.
      // Stripe facture un abonnement via une Invoice à chaque cycle de
      // renouvellement : les paiements d'abonnement sont donc déjà présents
      // ici (subscriptionId renseigné), on n'a pas besoin de les recompter
      // depuis l'objet subscription lui-même (voir computeEntityCohortRevenue
      // et heroSourceItems, qui ignorent désormais la "value" nominale d'un
      // abonnement : c'est la facture réellement payée qui fait foi).
      invoices: (invoicesData?.data || []).map((i) => ({
        ts: toTimestamp(i.created),
        // amount_paid seul (jamais amount_due en repli) : une facture non
        // payée ne doit contribuer aucun revenu, et le bloc "Factures —
        // Revenus" filtre de toute façon sur status === "paid".
        value: (i.amount_paid || 0) / 100,
        status: i.status,
        currency: (i.currency || "usd").toUpperCase(),
        customerId: i.customer || null,
        productId: extractLineProductId(i.lines?.data?.[0]),
        subscriptionId: extractInvoiceSubscriptionId(i),
      })),
      // status conservé ici (utilisé par le bloc "Nombre" des liens pour
      // les distinguer payé/en attente/expiré, et par le bloc héro pour
      // ne garder que les liens payés). currency conservée aussi : un
      // lien est créé en USD ou EUR (voir le sélecteur de devise de la
      // vue Liens), jamais en XOF — indispensable pour convertir
      // correctement vers la devise choisie dans le bloc héro.
      links: (Array.isArray(linksData) ? linksData : []).map((l) => ({
        ts: toTimestamp(l.created_at),
        value: l.amount || 0,
        status: l.status,
        currency: (l.currency || "USD").toUpperCase(),
      })),
      // status/source : utilisés par les blocs "Remboursements" (voir
      // computeRefundStats) — un remboursement n'est pas une transaction
      // séparée côté WalletTransaction, c'est le dépôt d'origine dont le
      // statut passe à "refunded" (routes/payout.py, refund_payment). source
      // distingue l'origine : "payment_link"/"invoice"/"subscription".
      balance: (walletData?.transactions || []).map((t) => ({
        ts: toTimestamp(t.created_at),
        value: t.direction === "out" ? -Math.abs(t.amount) : Math.abs(t.amount),
        status: t.status,
        source: t.source,
      })),
      totalBalance: Number(walletMeData?.available || 0),
    };
  }

  // "count" = nombre de buckets (24 pour "Jour", 7/30/365 pour semaine/mois/
  // année) ; bucketMs (heure ou jour, voir currentActivityPeriod) donne leur
  // taille — même logique de fenêtre quelle que soit la granularité.
  function computeActivityStats(items, count) {
    const bucketMs = currentActivityPeriod().bucketMs;
    const now = Date.now();
    const currentStart = now - count * bucketMs;
    const previousStart = now - 2 * count * bucketMs;
    const currentRevenueDaily = new Array(count).fill(0);
    const previousRevenueDaily = new Array(count).fill(0);
    const currentCountDaily = new Array(count).fill(0);
    const previousCountDaily = new Array(count).fill(0);
    let currentTotal = 0;
    let previousTotal = 0;
    let currentCount = 0;
    let previousCount = 0;

    items.forEach(({ ts, value }) => {
      if (ts == null) return;
      if (ts >= currentStart && ts <= now) {
        const idx = Math.min(count - 1, Math.max(0, Math.floor((ts - currentStart) / bucketMs)));
        currentRevenueDaily[idx] += value;
        currentCountDaily[idx] += 1;
        currentTotal += value;
        currentCount += 1;
      } else if (ts >= previousStart && ts < currentStart) {
        const idx = Math.min(count - 1, Math.max(0, Math.floor((ts - previousStart) / bucketMs)));
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

  // "Nouveaux clients — Revenus" et "Nouveaux produits — Revenus"
  // représentent l'argent réellement encaissé grâce à cette entité, acquise/
  // créée pendant la période — et seulement pendant cette même fenêtre —
  // plutôt qu'un champ Stripe cumulatif ou statique (total_spent du client,
  // prix catalogue du produit) qui grossit indéfiniment ou existe dès la
  // création, indépendamment de toute vente : ces deux biais favorisent les
  // cohortes les plus anciennes dans la comparaison actuel/précédent. Les
  // liens de paiement ne sont rattachés ni à un client ni à un produit
  // Stripe (voir fetchActivityRawData) : ils sont donc exclus de ce calcul,
  // qui ne porte que sur les factures payées, croisées par customerId ou
  // productId selon l'entité. Pas d'abonnements ici non plus : un abonnement
  // se règle via une Invoice à chaque cycle (déjà comptée ci-dessus), sa
  // "value" nominale ne représente aucun paiement réel — l'ajouter en plus
  // compterait ce revenu deux fois.
  // Commission Xepay par source, appliquée quand le filtre "Revenus" de
  // "Votre aperçu" est sur "net" : 6% sur les liens, 1% sur les factures/
  // abonnements — mêmes taux que heroNetMultiplier (backend : routes/
  // payments.py pour les liens, application_fee_percent dans
  // routes/webhook/stripe.py pour les factures/abonnements).
  function activityNetMultiplier(source) {
    if (activityNetMode !== "net") return 1;
    return source === "link" ? 0.94 : 0.99;
  }

  function computeEntityCohortRevenue(entities, paymentKeyField, count) {
    const bucketMs = currentActivityPeriod().bucketMs;
    const now = Date.now();
    const currentStart = now - count * bucketMs;
    const previousStart = now - 2 * count * bucketMs;

    const paymentsByKey = new Map();
    const addPayments = (list, isEligible) => {
      (list || []).forEach((p) => {
        const key = p[paymentKeyField];
        if (!key || p.ts == null || !isEligible(p.status)) return;
        if (!paymentsByKey.has(key)) paymentsByKey.set(key, []);
        paymentsByKey.get(key).push(p);
      });
    };
    // Toujours "invoice" comme source (jamais "link", voir plus haut) : le
    // taux net applicable à Clients/Produits est donc toujours celui des
    // factures/abonnements.
    addPayments(activityRaw.invoices, (status) => status === "paid");
    const multiplier = activityNetMultiplier("invoice");

    function revenueForWindow(entitiesInWindow, windowStart) {
      const daily = new Array(count).fill(0);
      let total = 0;
      entitiesInWindow.forEach((e) => {
        const payments = paymentsByKey.get(e.id) || [];
        const idx = Math.min(count - 1, Math.max(0, Math.floor((e.ts - windowStart) / bucketMs)));
        payments.forEach((p) => {
          if (p.ts < windowStart || p.ts >= windowStart + count * bucketMs) return;
          const amount = p.value * multiplier * getRate(p.currency || "USD", activityCurrency);
          daily[idx] += amount;
          total += amount;
        });
      });
      return { daily, total };
    }

    const currentEntities = entities.filter((e) => e.ts != null && e.ts >= currentStart && e.ts <= now);
    const previousEntities = entities.filter((e) => e.ts != null && e.ts >= previousStart && e.ts < currentStart);

    const current = revenueForWindow(currentEntities, currentStart);
    const previous = revenueForWindow(previousEntities, previousStart);

    return {
      currentRevenueDaily: current.daily,
      previousRevenueDaily: previous.daily,
      currentTotal: current.total,
      previousTotal: previous.total,
    };
  }

  function computeClientCohortRevenue(days) {
    return computeEntityCohortRevenue(activityRaw.clients || [], "customerId", days);
  }

  function computeProductRevenue(days) {
    return computeEntityCohortRevenue(activityRaw.products || [], "productId", days);
  }

  // Classement (pas de comparaison actuel/précédent ici) : parmi TOUTES les
  // entités (pas seulement celles créées dans la période, contrairement à
  // computeEntityCohortRevenue), celle qui a généré le plus de revenu via
  // des factures payées dans la période en cours. Utilisé par les blocs
  // "Meilleur client"/"Meilleur produit".
  function computeTopEntity(entities, paymentKeyField, count) {
    const bucketMs = currentActivityPeriod().bucketMs;
    const now = Date.now();
    const currentStart = now - count * bucketMs;
    const multiplier = activityNetMultiplier("invoice");
    const totals = new Map();
    (activityRaw.invoices || []).forEach((p) => {
      const key = p[paymentKeyField];
      if (!key || p.status !== "paid" || p.ts == null || p.ts < currentStart || p.ts > now) return;
      const amount = p.value * multiplier * getRate(p.currency || "USD", activityCurrency);
      totals.set(key, (totals.get(key) || 0) + amount);
    });
    let topKey = null;
    let topAmount = -Infinity;
    totals.forEach((amount, key) => {
      if (amount > topAmount) {
        topAmount = amount;
        topKey = key;
      }
    });
    if (topKey == null) return null;
    const entity = entities.find((e) => e.id === topKey);
    return { name: entity?.name || "—", amount: topAmount };
  }

  // Un remboursement n'a pas de notion de "brut"/"net" propre : le montant
  // WalletTransaction était déjà net de commission au moment du crédit
  // (voir fetchActivityRawData) — activityNetMode ne s'applique donc pas
  // ici, contrairement aux autres blocs de revenus.
  function computeRefundStats(source, count) {
    const bucketMs = currentActivityPeriod().bucketMs;
    const now = Date.now();
    const currentStart = now - count * bucketMs;
    const previousStart = now - 2 * count * bucketMs;
    const currentRevenueDaily = new Array(count).fill(0);
    const previousRevenueDaily = new Array(count).fill(0);
    let currentTotal = 0;
    let previousTotal = 0;

    (activityRaw.balance || []).forEach((t) => {
      if (t.ts == null || t.status !== "refunded" || t.source !== source) return;
      const amount = Math.abs(t.value) * getRate("XOF", activityCurrency);
      if (t.ts >= currentStart && t.ts <= now) {
        const idx = Math.min(count - 1, Math.max(0, Math.floor((t.ts - currentStart) / bucketMs)));
        currentRevenueDaily[idx] += amount;
        currentTotal += amount;
      } else if (t.ts >= previousStart && t.ts < currentStart) {
        const idx = Math.min(count - 1, Math.max(0, Math.floor((t.ts - previousStart) / bucketMs)));
        previousRevenueDaily[idx] += amount;
        previousTotal += amount;
      }
    });

    return { currentRevenueDaily, previousRevenueDaily, currentTotal, previousTotal };
  }

  // Revenu réel d'une catégorie filtrée par statut ("paid" pour les
  // factures, "active" pour les abonnements), avec conversion par devise
  // propre à chaque élément (une facture/un abonnement peut être en USD ou
  // EUR, voir fetchActivityRawData) — contrairement à computeActivityStats,
  // qui applique un taux fixe par catégorie et ne filtre aucun statut.
  // "source" détermine le taux de commission appliqué en mode "net" (voir
  // activityNetMultiplier) ; ignoré en mode "brut".
  function computeFilteredRevenueStats(items, count, isEligible, source) {
    const bucketMs = currentActivityPeriod().bucketMs;
    const now = Date.now();
    const currentStart = now - count * bucketMs;
    const previousStart = now - 2 * count * bucketMs;
    const currentRevenueDaily = new Array(count).fill(0);
    const previousRevenueDaily = new Array(count).fill(0);
    let currentTotal = 0;
    let previousTotal = 0;
    const multiplier = activityNetMultiplier(source);

    items.forEach(({ ts, value, currency, status }) => {
      if (ts == null || !isEligible(status)) return;
      const amount = value * multiplier * getRate(currency || "USD", activityCurrency);
      if (ts >= currentStart && ts <= now) {
        const idx = Math.min(count - 1, Math.max(0, Math.floor((ts - currentStart) / bucketMs)));
        currentRevenueDaily[idx] += amount;
        currentTotal += amount;
      } else if (ts >= previousStart && ts < currentStart) {
        const idx = Math.min(count - 1, Math.max(0, Math.floor((ts - previousStart) / bucketMs)));
        previousRevenueDaily[idx] += amount;
        previousTotal += amount;
      }
    });

    return { currentRevenueDaily, previousRevenueDaily, currentTotal, previousTotal };
  }

  function buildActivityLabels(count) {
    const { bucketMs } = currentActivityPeriod();
    const isHourly = bucketMs === HOUR_MS;
    const now = new Date();
    const labels = [];
    for (let i = count - 1; i >= 0; i--) {
      const d = new Date(now.getTime() - i * bucketMs);
      labels.push(
        isHourly
          ? d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })
          : d.toLocaleDateString("fr-FR", { day: "2-digit", month: "short" })
      );
    }
    return labels;
  }

  // Résout, pour un point d'un graphe "comparaison" (buildComparisonDatasets,
  // datasetIndex 0 = actuelle, 1 = précédente), sa date calendaire exacte au
  // lieu du texte générique "Période actuelle"/"Période précédente" dans le
  // tooltip. Le point précédent à l'index i correspond exactement à "days"
  // jours avant le point actuel au même index (mêmes bornes que
  // computeActivityStats : previousStart = now - 2*days, currentStart =
  // now - days).
  function buildComparisonDateResolver(count) {
    const { bucketMs } = currentActivityPeriod();
    const isHourly = bucketMs === HOUR_MS;
    const now = Date.now();
    return (datasetIndex, dataIndex) => {
      const bucketsAgo = count - 1 - dataIndex + (datasetIndex === 1 ? count : 0);
      const d = new Date(now - bucketsAgo * bucketMs);
      return isHourly
        ? d.toLocaleString("fr-FR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })
        : d.toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric" });
    };
  }

  function formatMoney(value, currency) {
    return value.toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " " + currency;
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
  // un seul "nombre de liens". Points cachés hors survol (pointRadius:0),
  // même comportement que buildComparisonDatasets sur tous les autres
  // blocs — demandé explicitement, malgré le fait qu'une courbe "En
  // attente"/"Expirés" à 0 toute la période devient une ligne plate sans
  // repère visuel distinct de l'axe.
  function buildLinksStatusDatasets(daily) {
    return [
      { label: "Payés", data: daily.paid, borderColor: "#16a34a", backgroundColor: "#16a34a", borderWidth: 2, pointRadius: 0, pointHoverRadius: 4, tension: 0.3, fill: false },
      { label: "En attente", data: daily.pending, borderColor: "#eab308", backgroundColor: "#eab308", borderWidth: 2, pointRadius: 0, pointHoverRadius: 4, tension: 0.3, fill: false },
      { label: "Expirés", data: daily.expired, borderColor: "#dc2626", backgroundColor: "#dc2626", borderWidth: 2, pointRadius: 0, pointHoverRadius: 4, tension: 0.3, fill: false },
    ];
  }

  // dateForPoint (optionnel) : résout la date exacte d'un point au lieu
  // d'utiliser dataset.label dans le tooltip — voir buildComparisonDateResolver.
  // Omis pour le graphe "Liens — Nombre par statut", dont les labels
  // ("Payés"/"En attente"/"Expirés") sont déjà ce qu'on veut afficher.
  // Tooltip HTML personnalisé réutilisant exactement le style du bloc héro
  // (.hero-chart-tooltip et consorts, voir heroTooltipHandler) au lieu du
  // tooltip Chart.js par défaut — un titre (yAxisLabel), un trait fin, puis
  // une ligne par dataset avec un point de la couleur de sa courbe et sa
  // valeur en gras. Toujours sous l'axe X, jamais sur le graphe.
  function activityTooltipHandler(context, tooltipId, dateForPoint, valueFormatter, title) {
    const { chart, tooltip } = context;
    const el = document.getElementById(tooltipId);
    if (!el) return;
    if (!tooltip || tooltip.opacity === 0 || !tooltip.dataPoints || !tooltip.dataPoints.length) {
      el.classList.remove("visible");
      return;
    }

    const rows = tooltip.dataPoints
      .map((dp) => {
        const dataset = chart.data.datasets[dp.datasetIndex];
        const label = dateForPoint ? dateForPoint(dp.datasetIndex, dp.dataIndex) : dataset.label;
        return `<div class="hero-chart-tooltip-row"><span class="hero-chart-tooltip-dot" style="background:${dataset.borderColor}"></span>${label} : <strong class="hero-chart-tooltip-value">${valueFormatter(dp.parsed.y)}</strong></div>`;
      })
      .join("");
    el.innerHTML = `
      <div class="hero-chart-tooltip-metric">${title}</div>
      <div class="hero-chart-tooltip-divider"></div>
      ${rows}
    `;
    el.classList.add("visible");

    const chartWidth = chart.width;
    const tooltipWidth = el.offsetWidth;
    let left = tooltip.caretX - tooltipWidth / 2;
    if (left < 0) left = 4;
    if (left + tooltipWidth > chartWidth) left = chartWidth - tooltipWidth - 4;
    el.style.left = left + "px";
    el.style.top = chart.chartArea.bottom + 8 + "px";
  }

  function renderOrUpdateChart(id, labels, datasets, valueFormatter, yAxisLabel, dateForPoint) {
    const canvas = document.getElementById(`activity-chart-${id}`);
    if (!canvas) return;
    const tooltipId = `activity-chart-tooltip-${id}`;
    const external = (context) => activityTooltipHandler(context, tooltipId, dateForPoint, valueFormatter, yAxisLabel);
    const xAxisTitle = `Période (${currentActivityPeriod().bucketMs === HOUR_MS ? "heure" : "jour"})`;

    if (activityCharts[id]) {
      const chart = activityCharts[id];
      chart.data.labels = labels;
      chart.data.datasets = datasets;
      chart.options.scales.x.title.text = xAxisTitle;
      chart.options.scales.y.title.text = yAxisLabel;
      chart.options.plugins.tooltip.external = external;
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
            enabled: false,
            external,
          },
        },
        scales: {
          x: {
            title: { display: true, text: xAxisTitle, color: "#6b7280", font: { size: 13, weight: "600" } },
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
  function computeLinksStatusDaily(items, count) {
    const bucketMs = currentActivityPeriod().bucketMs;
    const now = Date.now();
    const currentStart = now - count * bucketMs;
    const daily = { paid: new Array(count).fill(0), pending: new Array(count).fill(0), expired: new Array(count).fill(0) };

    items.forEach(({ ts, status }) => {
      if (ts == null || ts < currentStart || ts > now || !daily[status]) return;
      const idx = Math.min(count - 1, Math.max(0, Math.floor((ts - currentStart) / bucketMs)));
      daily[status][idx] += 1;
    });

    return daily;
  }

  async function renderCategory(cat, days) {
    let items = activityRaw ? activityRaw[cat.key] || [] : [];
    // Une facture de renouvellement d'abonnement (subscriptionId non nul)
    // appartient entièrement à "Abonnements", jamais à "Factures" — ni son
    // nombre, ni son revenu. Les deux catégories représentent deux
    // fonctionnalités métier distinctes (facturation ponctuelle vs
    // abonnement récurrent) : filtré ici, en amont, pour que "Nombre" et
    // "Revenus" comptent exactement la même population de factures.
    if (cat.key === "invoices") {
      items = items.filter((i) => i.subscriptionId == null);
    }
    const stats = computeActivityStats(items, days);
    const labels = buildActivityLabels(days);

    let curRevenue, prevRevenue, currentRevenueDaily, previousRevenueDaily;
    if (cat.key === "clients" || cat.key === "products") {
      const cohort = cat.key === "clients" ? computeClientCohortRevenue(days) : computeProductRevenue(days);
      curRevenue = cohort.currentTotal;
      prevRevenue = cohort.previousTotal;
      currentRevenueDaily = cohort.currentRevenueDaily;
      previousRevenueDaily = cohort.previousRevenueDaily;
    } else if (cat.key === "invoices") {
      const filtered = computeFilteredRevenueStats(items, days, (status) => status === "paid", "invoice");
      curRevenue = filtered.currentTotal;
      prevRevenue = filtered.previousTotal;
      currentRevenueDaily = filtered.currentRevenueDaily;
      previousRevenueDaily = filtered.previousRevenueDaily;
    } else if (cat.key === "subscriptions") {
      // La "value" nominale d'un abonnement n'est pas un paiement réel : on
      // somme plutôt les factures de renouvellement effectivement payées,
      // rattachées via subscriptionId (voir fetchActivityRawData) — datées
      // par leur propre date de règlement, pas la date de création de
      // l'abonnement.
      const subscriptionInvoices = (activityRaw.invoices || []).filter((i) => i.subscriptionId != null);
      const filtered = computeFilteredRevenueStats(subscriptionInvoices, days, (status) => status === "paid", "invoice");
      curRevenue = filtered.currentTotal;
      prevRevenue = filtered.previousTotal;
      currentRevenueDaily = filtered.currentRevenueDaily;
      previousRevenueDaily = filtered.previousRevenueDaily;
    } else {
      // "links" : un lien en attente/expiré n'est pas un revenu, et chaque
      // lien a sa propre devise (USD/EUR, jamais XOF — voir
      // fetchActivityRawData) plutôt qu'un taux fixe par catégorie.
      const filtered = computeFilteredRevenueStats(items, days, (status) => status === "paid", "link");
      curRevenue = filtered.currentTotal;
      prevRevenue = filtered.previousTotal;
      currentRevenueDaily = filtered.currentRevenueDaily;
      previousRevenueDaily = filtered.previousRevenueDaily;
    }

    const dateForPoint = buildComparisonDateResolver(days);

    const revId = activityCardId(cat, "revenue");
    if (visibleActivityBlocks.has(revId)) {
      setText(`activity-value-${revId}`, formatMoney(curRevenue, activityCurrency));
      setDelta(`activity-delta-${revId}`, curRevenue, prevRevenue);
      renderOrUpdateChart(
        revId,
        labels,
        buildComparisonDatasets(currentRevenueDaily, previousRevenueDaily),
        (v) => formatMoney(v, activityCurrency),
        `Revenus générés (${activityCurrency})`,
        dateForPoint
      );
    }

    const countId = activityCardId(cat, "count");
    if (visibleActivityBlocks.has(countId)) {
      setText(`activity-value-${countId}`, formatCount(stats.currentCount));
      setDelta(`activity-delta-${countId}`, stats.currentCount, stats.previousCount);
      if (cat.key === "links") {
        renderOrUpdateChart(countId, labels, buildLinksStatusDatasets(computeLinksStatusDaily(items, days)), formatCount, "Nombre (par statut)");
      } else {
        renderOrUpdateChart(countId, labels, buildComparisonDatasets(stats.currentCountDaily, stats.previousCountDaily), formatCount, "Nombre", dateForPoint);
      }
    }

    renderCatalogCards(cat, days, labels, dateForPoint);
  }

  // Blocs ajoutés via "+ Ajouter" pour cette catégorie (Meilleur client/
  // produit, Remboursements) — voir BLOCK_CATALOG.
  function renderCatalogCards(cat, days, labels, dateForPoint) {
    const refundSourceByCategory = { invoices: "invoice", subscriptions: "subscription", links: "payment_link" };

    if (cat.key === "clients" && visibleActivityBlocks.has("clients-top")) {
      const top = computeTopEntity(activityRaw.clients || [], "customerId", days);
      setText("activity-top-name-clients-top", top ? top.name : "—");
      setText("activity-top-amount-clients-top", top ? formatMoney(top.amount, activityCurrency) : "—");
    }
    if (cat.key === "products" && visibleActivityBlocks.has("products-top")) {
      const top = computeTopEntity(activityRaw.products || [], "productId", days);
      setText("activity-top-name-products-top", top ? top.name : "—");
      setText("activity-top-amount-products-top", top ? formatMoney(top.amount, activityCurrency) : "—");
    }

    const refundId = `${cat.key}-refunds`;
    const refundSource = refundSourceByCategory[cat.key];
    if (refundSource && visibleActivityBlocks.has(refundId)) {
      const refund = computeRefundStats(refundSource, days);
      setText(`activity-value-${refundId}`, formatMoney(refund.currentTotal, activityCurrency));
      setDelta(`activity-delta-${refundId}`, refund.currentTotal, refund.previousTotal);
      renderOrUpdateChart(
        refundId,
        labels,
        buildComparisonDatasets(refund.currentRevenueDaily, refund.previousRevenueDaily),
        (v) => formatMoney(v, activityCurrency),
        `Remboursements (${activityCurrency})`,
        dateForPoint
      );
    }
  }

  async function renderAllActivityCards() {
    if (!activityRaw) return;
    await Promise.all(ACTIVITY_CATEGORIES.map((cat) => renderCategory(cat, currentActivityPeriod().count)));
  }

  function rebuildActivityGrid() {
    const grid = document.getElementById("activity-grid");
    if (!grid) return;
    grid.innerHTML = buildActivityGridHTML();
    if (activityEditMode) {
      grid.querySelectorAll(".activity-card-remove").forEach((btn) => btn.classList.remove("d-none"));
    }
    renderAllActivityCards();
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
  // Plus de sélecteur de devise propre au bloc héro : il partage désormais
  // activityCurrency (le seul sélecteur de devise restant, dans les
  // filtres de "Votre aperçu"), pour n'avoir qu'une seule source de
  // vérité sur toute la vue.
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

  function countInRange(items, start, end) {
    return (items || []).filter(({ ts }) => ts != null && ts >= start && ts <= end).length;
  }

  // "Volume net" = montant payé moins la commission Xepay — 6% sur les
  // liens (voir le 0.94 déjà appliqué côté backend, routes/payments.py),
  // 1% sur les factures/abonnements (application_fee_percent/amount dans
  // routes/webhook/stripe.py) : le taux dépend de la source de l'item,
  // pas de la métrique elle-même.
  function heroNetMultiplier(source) {
    return source === "link" ? 0.94 : 0.99;
  }

  // Données brutes derrière chaque métrique héro : liens payés + factures
  // payées — toutes des sources de revenu réelles, contrairement à un lien
  // en attente/expiré ou une facture jamais payée. Pas de source "abonnement"
  // séparée : un abonnement se règle via une Invoice à chaque cycle, donc son
  // paiement réel est déjà dans paidInvoices (ajouter en plus la valeur
  // nominale de l'abonnement compterait ce revenu deux fois). "source"
  // distingue le taux de commission (heroNetMultiplier).
  function heroSourceItems(metric) {
    if (!activityRaw) return [];
    if (metric === "gross" || metric === "successful" || metric === "net") {
      const paidLinks = (activityRaw.links || []).filter((l) => l.status === "paid").map((l) => ({ ...l, source: "link" }));
      const paidInvoices = (activityRaw.invoices || []).filter((i) => i.status === "paid").map((i) => ({ ...i, source: "invoice" }));
      return [...paidLinks, ...paidInvoices];
    }
    if (metric === "clients") return activityRaw.clients || [];
    if (metric === "products") return activityRaw.products || [];
    return [];
  }

  // Valeur d'une métrique héro sur [start, end] : somme (montants, chacun
  // converti depuis SA PROPRE devise vers activityCurrency) ou comptage
  // selon l'unité (HERO_METRICS).
  function computeHeroValue(metric, start, end) {
    const items = heroSourceItems(metric);
    if (HERO_METRICS[metric].unit !== "currency") return countInRange(items, start, end);
    return items.reduce((sum, { ts, value, currency, source }) => {
      if (ts == null || ts < start || ts > end) return sum;
      const multiplier = metric === "net" ? heroNetMultiplier(source) : 1;
      return sum + value * multiplier * getRate(currency || "USD", activityCurrency);
    }, 0);
  }

  function formatHeroValue(metric, value) {
    return HERO_METRICS[metric].unit === "currency" ? formatMoney(value, activityCurrency) : formatCount(value);
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

    heroSourceItems(metric).forEach(({ ts, value, currency, source }) => {
      if (ts == null) return;
      const multiplier = metric === "net" ? heroNetMultiplier(source) : 1;
      const amount = isCount ? 1 : value * multiplier * getRate(currency || "USD", activityCurrency);
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

    // Toujours sous l'axe X (jamais dans/sur le graphe) : position
    // verticale fixe, juste sous la zone de tracé — seule la position
    // horizontale suit le point survolé, bornée pour ne pas sortir du
    // cadre du graphique.
    const chartWidth = chart.width;
    const tooltipWidth = el.offsetWidth;
    let left = tooltip.caretX - tooltipWidth / 2;
    if (left < 0) left = 4;
    if (left + tooltipWidth > chartWidth) left = chartWidth - tooltipWidth - 4;
    el.style.left = left + "px";
    el.style.top = chart.chartArea.bottom + 8 + "px";
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

    const compareStart = startOfDay(heroCompareDate).getTime();
    const compareValue = computeHeroValue(heroMetric, compareStart, compareStart + DAY_MS - 1);

    setText("metric-selector-label", HERO_METRICS[heroMetric].label);
    setText("granularity-selector-label", formatCompareDateLabel(heroCompareDate));
    setText("granularity-selector-amount", formatHeroValue(heroMetric, compareValue));
    setText("hero-stat-amount", formatHeroValue(heroMetric, value));
    setText("hero-stat-time", "Mis à jour à " + new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }));
    setText("hero-balance-amount", formatMoney((activityRaw?.totalBalance || 0) * getRate("XOF", activityCurrency), activityCurrency));

    renderHeroChart();
  }

  function closeHeroPopups() {
    document.getElementById("metric-popup")?.classList.add("d-none");
    document.getElementById("granularity-popup")?.classList.add("d-none");
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

  function closeActivityPopups() {
    document.getElementById("activity-currency-popup")?.classList.add("d-none");
    document.getElementById("activity-period-popup")?.classList.add("d-none");
    document.getElementById("activity-net-popup")?.classList.add("d-none");
    document.getElementById("activity-add-popup")?.classList.add("d-none");
  }

  // Les 3 filtres de "Votre aperçu" (devise, période précédente, revenus)
  // partagent le même mécanisme chevron -> popup -> sélection, repris du
  // bloc héro (voir initHeroStat) : un seul wiring générique plutôt que 3
  // blocs de click-listeners identiques.
  function wireActivityFilter(btnId, popupId, onSelect) {
    const btn = document.getElementById(btnId);
    const popup = document.getElementById(popupId);
    if (!btn || !popup) return;
    on(btn, "click", (e) => {
      e.stopPropagation();
      const wasOpen = !popup.classList.contains("d-none");
      closeActivityPopups();
      popup.classList.toggle("d-none", wasOpen);
    });
    popup.querySelectorAll(".activity-filter-item").forEach((item) => {
      on(item, "click", () => {
        popup.querySelectorAll(".activity-filter-item").forEach((b) => b.classList.toggle("active", b === item));
        onSelect(item);
        closeActivityPopups();
        renderAllActivityCards();
      });
    });
  }

  // Liste, dans le popup "+ Ajouter", tout bloc (par défaut ou catalogue)
  // actuellement masqué — reconstruit à chaque ouverture, puisque la liste
  // change selon ce qui est déjà affiché.
  function buildAddPopupHTML() {
    const hidden = [...DEFAULT_BLOCKS, ...BLOCK_CATALOG].filter((b) => !visibleActivityBlocks.has(b.id));
    if (!hidden.length) {
      return `<div class="activity-filter-item activity-filter-item-empty">Tous les blocs sont déjà affichés</div>`;
    }
    return hidden.map((b) => `<button type="button" class="activity-filter-item" data-add="${b.id}">${b.label}</button>`).join("");
  }

  // Affiche/masque le bouton "x" de chaque bloc visible — n'importe quel
  // bloc (par défaut ou ajouté) est retirable, pas seulement ceux du
  // catalogue, voir la demande initiale ("ajouter/retirer... selon son bon
  // vouloir").
  function toggleActivityEditMode() {
    activityEditMode = !activityEditMode;
    document.querySelectorAll(".activity-card-remove").forEach((btn) => btn.classList.toggle("d-none", !activityEditMode));
    setText("activity-edit-label", activityEditMode ? "Terminé" : "Modifier");
  }

  async function initActivitySection() {
    const grid = document.getElementById("activity-grid");
    if (!grid) return;
    grid.innerHTML = buildActivityGridHTML();

    // Délégué sur la grille entière (pas sur chaque bouton) : elle est
    // reconstruite (innerHTML) à chaque ajout/retrait de bloc, un listener
    // par carte serait perdu à la reconstruction suivante.
    on(grid, "click", (e) => {
      const removeBtn = e.target.closest(".activity-card-remove");
      if (!removeBtn) return;
      visibleActivityBlocks.delete(removeBtn.dataset.remove);
      saveVisibleBlocks();
      rebuildActivityGrid();
    });

    on(document.getElementById("activity-edit-btn"), "click", toggleActivityEditMode);

    on(document.getElementById("activity-add-btn"), "click", (e) => {
      e.stopPropagation();
      const popup = document.getElementById("activity-add-popup");
      const wasOpen = !popup.classList.contains("d-none");
      closeActivityPopups();
      if (wasOpen) return;
      popup.innerHTML = buildAddPopupHTML();
      popup.querySelectorAll("[data-add]").forEach((item) => {
        on(item, "click", () => {
          visibleActivityBlocks.add(item.dataset.add);
          saveVisibleBlocks();
          closeActivityPopups();
          rebuildActivityGrid();
        });
      });
      popup.classList.remove("d-none");
    });

    wireActivityFilter("activity-currency-btn", "activity-currency-popup", (item) => {
      activityCurrency = item.dataset.currency;
      setText("activity-currency-label", item.dataset.currency);
      // Seul sélecteur de devise restant (le bloc héro n'a plus le sien) :
      // le rafraîchir aussi ici.
      renderHeroStat();
    });
    wireActivityFilter("activity-period-btn", "activity-period-popup", (item) => {
      activityPeriodKey = item.dataset.period;
      setText("activity-period-label", item.textContent);
    });
    wireActivityFilter("activity-net-btn", "activity-net-popup", (item) => {
      activityNetMode = item.dataset.net;
      setText("activity-net-label", item.textContent);
    });
    on(document, "click", closeActivityPopups);

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
