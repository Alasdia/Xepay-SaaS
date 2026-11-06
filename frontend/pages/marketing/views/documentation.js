export const title = "Xepay — Documentation";

const GUIDES = [
  {
    title: "Créer un lien de paiement",
    summary: "Encaisser un client sans site web",
    steps: [
      "Dans la sidebar de votre dashboard, cliquez sur <strong>Mes liens de paiement</strong>.",
      "Cliquez sur le bouton <strong>Créer un lien</strong>.",
      "Renseignez le montant (fixe ou libre) et la devise, puis validez.",
      "Copiez le lien généré et partagez-le à votre client (WhatsApp, email, réseaux sociaux).",
    ],
  },
  {
    title: "Configurer votre compte Stripe Connect",
    summary: "Obligatoire avant de pouvoir encaisser et retirer",
    steps: [
      "Cliquez sur l'icône ⚙️ dans le bandeau en haut de votre dashboard.",
      "Dans Paramètres, ouvrez l'onglet <strong>Compte Stripe Connect</strong>.",
      "Cliquez sur <strong>Configurer Stripe</strong> et suivez le parcours de vérification (KYC) proposé par Stripe.",
      "Une fois validé, votre statut passe à \"Activé\" — vous pouvez encaisser et retirer.",
    ],
  },
  {
    title: "Retirer vos fonds",
    summary: "Envoyer votre solde vers votre compte bancaire",
    steps: [
      "Dans la sidebar, cliquez sur <strong>Solde</strong>.",
      "Cliquez sur le bouton <strong>Retirer des fonds</strong>.",
      "Indiquez le montant à retirer et confirmez.",
      "Le retrait est envoyé par Stripe vers le compte bancaire enregistré sur votre compte Connect — vous pouvez l'annuler tant qu'il n'est pas finalisé.",
    ],
  },
  {
    title: "Suivre vos transactions",
    summary: "Historique, filtres et détail de chaque paiement",
    steps: [
      "Dans la sidebar, cliquez sur <strong>Transactions</strong> pour dérouler le sous-menu.",
      "Choisissez <strong>Paiements</strong> pour vos encaissements, ou <strong>Retraits</strong> pour vos virements sortants.",
      "Filtrez par devise, statut ou date depuis la vue.",
      "Cliquez sur une ligne pour en voir le détail complet.",
    ],
  },
  {
    title: "Gérer votre activité commerciale",
    summary: "Clients, produits, abonnements, factures et moyens de paiement",
    steps: [
      "Dans la sidebar, ouvrez la section <strong>Commerce</strong>.",
      "Choisissez la rubrique voulue : <strong>Clients</strong>, <strong>Produits</strong>, <strong>Abonnements</strong>, <strong>Factures</strong>, <strong>Moyens de paiement</strong> ou <strong>Risque</strong>.",
      "Chaque rubrique s'ouvre dans sa propre page, avec ses propres actions de création/gestion.",
    ],
  },
  {
    title: "Inviter un membre de votre équipe",
    summary: "Donner un accès à un collaborateur, avec un rôle défini — plan Business",
    steps: [
      "Cliquez sur l'icône ⚙️ dans le bandeau en haut de votre dashboard.",
      "Dans Paramètres, ouvrez l'onglet <strong>Équipe et sécurité</strong>.",
      "Cliquez sur <strong>Inviter un membre</strong>, renseignez son email et choisissez son rôle.",
      "Le membre reçoit une invitation par email pour rejoindre votre espace de travail.",
    ],
  },
  {
    title: "Activer la double authentification (2FA)",
    summary: "Sécuriser l'accès à votre compte",
    steps: [
      "Cliquez sur l'icône ⚙️ dans le bandeau en haut de votre dashboard.",
      "Dans Paramètres, ouvrez l'onglet <strong>Authentification</strong>.",
      "Activez la 2FA par application, ou enregistrez une clé de sécurité (passkey).",
      "Conservez vos codes de secours dans un endroit sûr — ils permettent de récupérer l'accès si vous perdez votre méthode principale.",
    ],
  },
  {
    title: "Générer une clé API",
    summary: "Intégrer Xepay à votre propre site ou application — plan Pro",
    steps: [
      "Dans la sidebar, cliquez sur <strong>API Access</strong>.",
      "Générez votre clé API publique et secrète depuis cette page.",
      "Configurez une URL de webhook si vous voulez recevoir les événements en temps réel.",
      "Conservez votre clé secrète en sécurité — elle ne sera plus affichée en clair par la suite.",
    ],
  },
];

function guideItemHtml(g, i) {
  return `
  <details class="faq-item guide-item"${i === 0 ? " open" : ""}>
    <summary>${g.title}<span class="guide-item-summary">${g.summary}</span></summary>
    <ol>
      ${g.steps.map((s) => `<li>${s}</li>`).join("")}
    </ol>
  </details>`;
}

export function render() {
  return `
<section class="page-hero reveal">
  <div class="eyebrow">Documentation</div>
  <h1>Tout pour <mark>utiliser Xepay</mark>.</h1>
  <p>Pour chaque action courante, le chemin exact à suivre dans votre dashboard, étape par étape.</p>
</section>

<section class="faq-section reveal">
  <div class="section-tag">Guides étape par étape</div>
  ${GUIDES.map(guideItemHtml).join("")}
</section>

<div class="feat-grid">
  <div class="feat-card reveal">
    <div class="section-tag">Sans code</div>
    <h3>Liens de paiement</h3>
    <p class="fc-sub">Aucune intégration technique nécessaire : créez un lien de paiement depuis votre dashboard et partagez-le directement. C'est la façon la plus rapide de commencer à encaisser.</p>
  </div>
  <div class="feat-card reveal">
    <div class="section-tag">Avec code</div>
    <h3>Clés API & webhooks</h3>
    <p class="fc-sub">Pour intégrer Xepay à votre propre site ou application, générez une clé API depuis vos paramètres et configurez vos webhooks pour recevoir les événements de paiement en temps réel. Voir la page API pour la vue d'ensemble.</p>
    <a href="/api" class="plan-cta ghost" style="margin-top:12px;display:inline-block;">Voir la page API →</a>
  </div>
</div>

<div class="disclaimer-strip reveal">
  <div>📘</div>
  <div><strong>Référence technique complète à venir.</strong> En attendant, notre équipe peut vous accompagner directement sur votre intégration — écrivez à <a href="mailto:support@alasdia.com">support@alasdia.com</a>.</div>
</div>
`;
}
