// Skeletons de navigation SPA — un par vue, structurés comme le TEMPLATE
// réel de la vue correspondante (spa/views/*.js) pour que la transition
// skeleton -> contenu ne déplace pas visuellement les blocs.
// Styles : skeleton.css (chargé en permanence par dashboard.html).

const line = (width = 100, extra = "") =>
  `<div class="sk-shimmer sk-line ${extra} sk-w-${width}"></div>`;

const btn = (extra = "") => `<div class="sk-shimmer sk-btn ${extra}"></div>`;

// En-tête commun aux 7 vues : titre + sous-titre à gauche, actions à droite.
const head = (actions = 1) => `
<div class="sk-head">
  <div class="sk-w-50">
    ${line(35, "lg")}
    ${line(75, "sm")}
  </div>
  <div class="sk-head-actions">
    ${Array.from({ length: actions }, () => btn()).join("")}
  </div>
</div>`;

// Carte type KPI : libellé court + valeur en gras.
const kpiCard = () => `
<div class="sk-card">
  ${line(50, "sm")}
  ${line(75, "lg")}
  ${line(35, "sm")}
</div>`;

const tableCard = (rows = 6) => `
<div class="sk-card">
  <div class="sk-between" style="margin-bottom: 18px;">
    ${line(25)}
    ${btn("sm")}
  </div>
  ${Array.from(
    { length: rows },
    () => `
  <div class="sk-tr">
    <div class="sk-inline">
      <div class="sk-shimmer sk-circle"></div>
      <div style="flex: 1;">
        ${line(60, "sm")}
        ${line(35, "sm")}
      </div>
    </div>
    ${line(60, "sm")}
    <div class="sk-shimmer sk-badge"></div>
    ${line(75, "sm")}
    ${line(50, "sm")}
  </div>`
  ).join("")}
</div>`;

// Carte de formulaire : titre + champs libellés.
const formCard = (fields = 3) => `
<div class="sk-card">
  ${line(50)}
  <div class="sk-stack" style="margin-top: 20px;">
    ${Array.from(
      { length: fields },
      () => `
    <div>
      ${line(25, "sm")}
      <div class="sk-shimmer sk-input sk-w-100" style="margin-top: 8px;"></div>
    </div>`
    ).join("")}
    <div class="sk-shimmer sk-btn sk-w-100"></div>
  </div>
</div>`;

// En-tête + ligne de 3 KPI + tableau (voir .subview-sticky-intro avec
// ligne de KPI, commerce.js) - partagé par Clients/Produits/Abonnements/
// Factures/Moyens de paiement, seuls actions/rows diffèrent entre elles.
const kpiTablePage = (actions = 1, rows = 6) => `
${head(actions)}
<div class="sk-row cols-3">
  ${kpiCard()}${kpiCard()}${kpiCard()}
</div>
${tableCard(rows)}`;

const SKELETONS = {
  // Accueil : bandeau d'usage, 3 cartes wallet, jauge de plan, graphique.
  dashboard: () => `
${head(2)}
<div class="sk-card sk-between" style="margin-bottom: 16px;">
  ${line(60, "sm")}
  ${btn("sm")}
</div>
<div class="sk-row cols-3">
  ${kpiCard()}${kpiCard()}${kpiCard()}
</div>
<div class="sk-card">
  <div class="sk-between" style="margin-bottom: 14px;">
    ${line(35, "sm")}
    ${line(15, "sm")}
  </div>
  <div class="sk-shimmer sk-line sm sk-w-100"></div>
</div>
<div class="sk-card">
  ${line(25)}
  <div class="sk-shimmer sk-chart sk-w-100" style="margin-top: 18px;"></div>
</div>`,

  // Transactions : 4 boutons d'export, 3 KPI, graphique + table d'activité.
  transactions: () => `
${head(4)}
<div class="sk-row cols-3">
  ${kpiCard()}${kpiCard()}${kpiCard()}
</div>
<div class="sk-card">
  ${line(25)}
  <div class="sk-shimmer sk-chart sk-w-100" style="margin-top: 18px;"></div>
</div>
${tableCard(6)}`,

  // Liens : compteur de liens + cartes de liens empilées.
  liens: () => `
${head(1)}
<div class="sk-card">
  <div class="sk-between" style="margin-bottom: 12px;">
    ${line(35, "sm")}
    ${line(15, "sm")}
  </div>
  <div class="sk-shimmer sk-line sm sk-w-100"></div>
</div>
<div class="sk-stack">
  ${Array.from(
    { length: 4 },
    () => `
  <div class="sk-card sk-between">
    <div style="flex: 1;">
      ${line(50)}
      ${line(90, "sm")}
    </div>
    <div class="sk-head-actions">
      ${btn("sm")}${btn("sm")}
    </div>
  </div>`
  ).join("")}
</div>`,

  // API : 3 KPI, clés + logs sur 2 colonnes, table de webhooks, doc.
  api: () => `
${head(1)}
<div class="sk-row cols-3">
  ${kpiCard()}${kpiCard()}${kpiCard()}
</div>
<div class="sk-row cols-2">
  <div class="sk-card">
    ${line(35)}
    <div class="sk-stack" style="margin-top: 18px;">
      <div class="sk-shimmer sk-input sk-w-100"></div>
      <div class="sk-shimmer sk-input sk-w-100"></div>
      <div class="sk-head-actions">${btn("sm")}${btn("sm")}</div>
    </div>
  </div>
  <div class="sk-card">
    ${line(35)}
    <div class="sk-stack" style="margin-top: 18px;">
      ${line(90, "sm")}${line(75, "sm")}${line(90, "sm")}${line(60, "sm")}
    </div>
  </div>
</div>
${tableCard(4)}
<div class="sk-card">
  ${line(35, "lg")}
  <div class="sk-stack" style="margin-top: 18px;">
    ${line(60, "sm")}
    <div class="sk-shimmer sk-chart sk-w-100" style="height: 120px;"></div>
    ${line(50, "sm")}
    <div class="sk-shimmer sk-chart sk-w-100" style="height: 120px;"></div>
  </div>
</div>`,

  // Profil : jauge de complétion + cartes KYC/Stripe sur 2 colonnes.
  profil: () => `
<div class="sk-head">
  <div class="sk-w-50">
    ${line(35, "lg")}
    ${line(75, "sm")}
  </div>
  <div style="width: 150px;">
    ${line(60, "sm")}
    <div class="sk-shimmer sk-line sm sk-w-100" style="margin-top: 8px;"></div>
  </div>
</div>
<div class="sk-row cols-2">
  <div class="sk-card">
    <div class="sk-between" style="margin-bottom: 16px;">
      ${line(50)}
      <div class="sk-shimmer sk-badge"></div>
    </div>
    ${line(90, "sm")}
    <div class="sk-shimmer sk-btn sk-w-100" style="margin-top: 20px;"></div>
  </div>
  <div class="sk-card">
    <div class="sk-between" style="margin-bottom: 16px;">
      ${line(50)}
      <div class="sk-shimmer sk-badge"></div>
    </div>
    ${line(90, "sm")}
    ${line(75, "sm")}
    <div class="sk-shimmer sk-btn sk-w-100" style="margin-top: 20px;"></div>
  </div>
  ${formCard(3)}
  ${formCard(2)}
</div>`,

  // Sécurité : mot de passe / sessions à gauche, 2FA / journal à droite.
  securite: () => `
<div class="sk-head">
  <div class="sk-w-50">
    ${line(35, "lg")}
    ${line(75, "sm")}
  </div>
  <div class="sk-shimmer sk-badge" style="width: 150px;"></div>
</div>
<div class="sk-row cols-2">
  <div class="sk-stack">
    ${formCard(3)}
    <div class="sk-card">
      ${line(50)}
      <div class="sk-card" style="margin-top: 16px;">
        <div class="sk-between">
          <div style="flex: 1;">
            ${line(60, "sm")}
            ${line(35, "sm")}
          </div>
          <div class="sk-shimmer sk-badge"></div>
        </div>
      </div>
      <div class="sk-shimmer sk-btn sk-w-100" style="margin-top: 16px;"></div>
    </div>
  </div>
  <div class="sk-stack">
    <div class="sk-card">
      <div class="sk-between" style="margin-bottom: 16px;">
        ${line(60)}
        <div class="sk-shimmer sk-badge"></div>
      </div>
      ${line(90, "sm")}
      <div class="sk-shimmer sk-btn sk-w-100" style="margin-top: 20px;"></div>
    </div>
    <div class="sk-card">
      ${line(50)}
      <div class="sk-stack" style="margin-top: 18px;">
        ${line(90, "sm")}${line(75, "sm")}${line(90, "sm")}${line(60, "sm")}
      </div>
    </div>
  </div>
</div>`,

  // Sous-vues Commerce avec KPI (bandeau sticky + ligne de KPI + tableau -
  // voir commerce.js/renderClients|renderProducts|...). Clients/Produits/
  // Abonnements/Factures ont un bouton "+ Créer..." (actions:1) ; Moyens
  // de paiement n'en a pas (actions:0, voir commerce.js).
  clients: () => kpiTablePage(1),
  produits: () => kpiTablePage(1),
  abonnements: () => kpiTablePage(1),
  factures: () => kpiTablePage(1),
  "moyens-paiement": () => kpiTablePage(0, 5),

  // Risque : bandeau sticky SANS ligne de KPI (.subview-sticky-intro--compact),
  // juste un tableau (litiges/alertes).
  risque: () => `
${head(0)}
${tableCard(6)}`,

  // Shopify : bandeau sticky compact + barre de 4 onglets (Produits/
  // Commandes/Clients/Configuration, voir SHOPIFY_TABS) + tableau de
  // l'onglet actif.
  shopify: () => `
${head(0)}
<div class="sk-chips" style="margin-bottom: 18px;">
  ${Array.from({ length: 4 }, () => `<div class="sk-shimmer sk-badge" style="width: 90px;"></div>`).join("")}
</div>
${tableCard(5)}`,

  // Mon entreprise : bandeau de statut (icône + statut + étapes), puis
  // récap officiel/documents à gauche, fondateur à droite (voir
  // monEntreprise.js/render).
  "mon-entreprise": () => `
<div class="sk-card" style="margin-bottom: 16px;">
  <div class="sk-inline" style="margin-bottom: 14px;">
    <div class="sk-shimmer sk-circle"></div>
    <div style="flex: 1;">
      ${line(35, "sm")}
      ${line(50, "sm")}
    </div>
  </div>
  ${line(90, "sm")}
</div>
<div class="sk-row cols-2">
  <div class="sk-stack">
    ${formCard(3)}
    ${formCard(2)}
  </div>
  <div class="sk-stack">
    ${formCard(2)}
  </div>
</div>`,

  // Solde : liste des 4 soldes par source à gauche + grand solde
  // principal, historique wallet + rapports à droite (voir solde.js/
  // TEMPLATE).
  solde: () => `
${head(0)}
<div class="sk-row cols-2">
  <div class="sk-stack">
    <div class="sk-card">
      ${Array.from(
        { length: 4 },
        () => `
      <div class="sk-between" style="margin-bottom: 14px;">
        ${line(35, "sm")}
        ${line(15, "sm")}
      </div>`
      ).join("")}
    </div>
    <div class="sk-card">
      ${line(35)}
      ${line(60, "lg")}
      <div class="sk-shimmer sk-line sm sk-w-100" style="margin-top: 14px;"></div>
    </div>
  </div>
  <div class="sk-stack">
    ${formCard(1)}
    ${formCard(1)}
  </div>
</div>`,

  // Paramètres (accueil) : titre + 3 sections de tuiles cliquables (voir
  // parametres.js/overviewTemplate) - une grille de tuiles icône+texte par
  // section, jamais de KPI/tableau ici.
  parametres: () => `
${line(35, "lg")}
${[3, 3, 2].map((count) => `
<div class="sk-card" style="margin: 20px 0 16px;">
  ${line(25)}
  <div class="sk-row cols-${count}" style="margin-top: 14px; margin-bottom: 0;">
    ${Array.from(
      { length: count },
      () => `
    <div class="sk-inline">
      <div class="sk-shimmer sk-circle"></div>
      <div style="flex: 1;">
        ${line(75, "sm")}
        ${line(90, "sm")}
      </div>
    </div>`
    ).join("")}
  </div>
</div>`).join("")}`,

  // Paramètres > détail (voir parametres.js/detailHeader) : UNE seule
  // route ("parametres-detail") sert toutes les sections (compte/équipe/
  // sécurité/stripe/commission/entreprise/permissions/shopify/retraits) -
  // fil d'Ariane réduit + cartes de contenu génériques, faute de pouvoir
  // distinguer la section ciblée depuis le seul nom de route.
  "parametres-detail": () => `
${line(25, "sm")}
<div style="margin-top: 16px;">
  ${formCard(3)}
  ${formCard(2)}
</div>`,
};

// Détail d'une transaction (Paiement ou Retrait, voir transactionDetail.js) -
// bouton retour + titre/sous-titre + liste de lignes libellé/valeur.
const transactionDetailSkeleton = () => `
${head(0)}
<div class="sk-card">
  <div class="sk-shimmer sk-btn sm" style="margin-bottom: 18px;"></div>
  ${line(35, "lg")}
  ${line(60, "sm")}
  <div class="sk-stack" style="margin-top: 20px;">
    ${Array.from(
      { length: 6 },
      () => `
    <div class="sk-between">
      ${line(25, "sm")}
      ${line(35, "sm")}
    </div>`
    ).join("")}
  </div>
</div>`;
SKELETONS["transaction-paiement-detail"] = transactionDetailSkeleton;
SKELETONS["transaction-retrait-detail"] = transactionDetailSkeleton;

// Paiements/Retraits (voir app.js) utilisent exactement mountTransactions,
// comme /transactions - même skeleton, pas de duplication.
SKELETONS.paiements = SKELETONS.transactions;
SKELETONS.retraits = SKELETONS.transactions;

// Les 6 sous-vues Liens (voir LIEN_SECTIONS, views/liens.js) ont toutes
// exactement le même gabarit que /liens, seul le filtre usage/montant
// change - même skeleton pour les 6.
["unique-fixe", "unique-libre", "quota-fixe", "quota-libre", "illimite-fixe", "illimite-libre"].forEach((key) => {
  SKELETONS[key] = SKELETONS.liens;
});

// Repli neutre : en-tête + cartes génériques (route inconnue du mapping).
const FALLBACK = () => `
${head(1)}
<div class="sk-row cols-3">
  ${kpiCard()}${kpiCard()}${kpiCard()}
</div>
${tableCard(5)}`;

export function getSkeleton(routeName) {
  return (SKELETONS[routeName] || FALLBACK)();
}
