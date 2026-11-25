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

// Bloc de lignes libellé/valeur (voir .params-info-row, parametres.js) -
// pour les sections Paramètres qui affichent des infos en lecture, pas
// un formulaire (formCard a des champs input, pas ce qu'affichent par
// ex. Coordonnées ou Code de sauvegarde).
const infoRowsCard = (rows = 3) => `
<div class="sk-card">
  ${Array.from(
    { length: rows },
    () => `
  <div class="sk-between" style="margin-bottom: 14px;">
    ${line(35, "sm")}
    ${line(25, "sm")}
  </div>`
  ).join("")}
</div>`;

// Barre de chips (voir .notif-tabs/.shopify-tab, même mécanisme d'onglet
// que la barre Shopify) - pour les sections Paramètres qui ont leurs
// propres onglets internes (Notifications, Compte Stripe).
const chipsRow = (count = 3) => `
<div class="sk-chips" style="margin: 16px 0 20px;">
  ${Array.from({ length: count }, () => `<div class="sk-shimmer sk-badge" style="width: 100px;"></div>`).join("")}
</div>`;

// En-tête de sous-section avec bouton d'action (voir
// .params-subsection-header, parametres.js) - répété plusieurs fois
// dans Authentification (Google/2FA/Clés d'accès).
const subsectionHeaderWithBtn = () => `
<div class="sk-between" style="margin: 20px 0 10px;">
  ${line(35, "sm")}
  ${btn("sm")}
</div>
${line(75, "sm")}`;

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

  // Paramètres > détail (voir parametres.js/detailHeader) - repli
  // générique UNIQUEMENT si params.section n'est reconnue par aucune
  // des 10 entrées "parametres-detail:<section>" ci-dessous (ex. URL
  // avec une section invalide/retirée).
  "parametres-detail": () => `
${line(25, "sm")}
<div style="margin-top: 16px;">
  ${formCard(3)}
  ${formCard(2)}
</div>`,

  // Les 10 sections de Paramètres (voir overviewTemplate, parametres.js)
  // ont chacune leur disposition réelle - routées via params.section
  // (getSkeleton), puisque "parametres-detail" seul ne les distingue pas.

  // Coordonnées/mot de passe (lignes libellé/valeur) + sessions actives
  // + workspaces (2 mini-tableaux, voir informationsPersonnellesTemplate).
  "parametres-detail:informations-personnelles": () => `
${line(25, "sm")}
${infoRowsCard(3)}
${infoRowsCard(1)}
${tableCard(3)}
${tableCard(3)}`,

  // Google / 2FA / Clés d'accès (3 sous-sections à bouton) + tableau des
  // clés d'accès (voir authentificationTemplate).
  "parametres-detail:authentification": () => `
${line(25, "sm")}
${line(90, "sm")}
${subsectionHeaderWithBtn()}
${subsectionHeaderWithBtn()}
${subsectionHeaderWithBtn()}
${tableCard(3)}`,

  // Catégories en onglets (7, voir NOTIFICATION_CATEGORIES) + tableau
  // Email/SMS/Push de la catégorie active (voir notificationsTemplate).
  "parametres-detail:notifications": () => `
${line(25, "sm")}
${line(90, "sm")}
${chipsRow(7)}
${tableCard(5)}`,

  // Compte Stripe Connect : ses propres onglets internes (voir
  // stripeTabsHtml) + champs (voir stripeTemplate).
  "parametres-detail:stripe": () => `
${line(25, "sm")}
${line(90, "sm")}
${chipsRow(2)}
${formCard(3)}`,

  // Volume/taux + paliers de commission (voir commissionTemplate).
  "parametres-detail:commission": () => `
${line(25, "sm")}
${line(90, "sm")}
<div class="sk-card">
  ${Array.from({ length: 2 }, () => `
  <div class="sk-between" style="margin-bottom: 14px;">
    ${line(35, "sm")}
    ${line(25, "sm")}
  </div>`).join("")}
  <div class="sk-shimmer sk-chart sk-w-100" style="height: 90px; margin-top: 10px;"></div>
</div>`,

  // Membres de l'équipe (tableau) + journal d'activité (second tableau,
  // voir equipeTemplate).
  "parametres-detail:equipe": () => `
${line(25, "sm")}
<div class="sk-between" style="margin: 14px 0;">
  ${line(60, "sm")}
  ${btn("sm")}
</div>
${tableCard(4)}
${line(25, "sm")}
${tableCard(4)}`,

  // Carte promo Buildness (LLC US) + widget Stripe de la société (voir
  // entrepriseTemplate).
  "parametres-detail:entreprise": () => `
${line(25, "sm")}
<div class="sk-card" style="margin-bottom: 24px;">
  <div class="sk-inline">
    <div class="sk-shimmer sk-circle"></div>
    <div style="flex: 1;">
      ${line(50, "sm")}
      ${line(75, "sm")}
    </div>
  </div>
  <div class="sk-shimmer sk-btn sk-w-100" style="margin-top: 16px;"></div>
</div>
<div class="sk-between" style="margin-bottom: 10px;">
  ${line(50, "sm")}
  ${btn("sm")}
</div>
${formCard(2)}`,

  // Carte promo de connexion Shopify (voir shopifyTemplate, renvoie vers
  // l'onglet Shopify de Commerce une fois connecté).
  "parametres-detail:shopify": () => `
${line(25, "sm")}
${line(90, "sm")}
${formCard(2)}`,

  // Rôle minimal requis par action sensible (tableau, voir
  // permissionsTemplate).
  "parametres-detail:permissions": () => `
${line(25, "sm")}
${line(90, "sm")}
${tableCard(5)}`,

  // Verto (virement UEMOA) - comptes bancaires puis retrait, 2 étapes
  // (voir retraitsTemplate).
  "parametres-detail:retraits": () => `
${line(25, "sm")}
${line(90, "sm")}
${formCard(2)}
${formCard(2)}`,
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

// routeName seul ne suffit pas pour "parametres-detail" : une seule
// route sert ses 10 sections (:section), chacune avec une disposition
// réellement différente (voir les entrées "parametres-detail:<section>"
// dans SKELETONS ci-dessus) - params.section (transmis par router.js,
// lui-même déjà disponible via la destructuration de "found" juste
// avant l'appel) permet de choisir la bonne au lieu de retomber sur une
// approximation générique partagée par les 10.
export function getSkeleton(routeName, params = {}) {
  const sectionKey = params.section ? `${routeName}:${params.section}` : null;
  const render = (sectionKey && SKELETONS[sectionKey]) || SKELETONS[routeName] || FALLBACK;
  return render();
}
