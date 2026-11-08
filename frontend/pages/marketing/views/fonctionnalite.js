export const title = "Xepay — Fonctionnalités";

export function render() {
  return `
<section class="page-hero reveal">
  <div class="eyebrow">Toutes les fonctionnalités</div>
  <h1>Né en Afrique de l'Ouest, <mark>connecté au monde</mark>.</h1>
  <p>Une plateforme fintech mondiale pensée pour la zone UEMOA — XOF, USD, EUR — sans friction, sans barrière.</p>
  <div class="africa-badge">
    <div class="flag">🇸🇳🇨🇮🇧🇯🇧🇫🇳🇪🇹🇬🇬🇼🇲🇱</div>
    <div class="sep"></div>
    <div class="text">ZONE UEMOA — 8 PAYS</div>
    <div class="sep"></div>
    <div class="xof-pill">XOF · USD · EUR</div>
  </div>
</section>

<section id="paiement-en-ligne" class="feature-block reveal">
  <div class="feature-inner">
    <div class="feature-icon">🛒</div>
    <div class="section-tag">Paiements</div>
    <h2>Paiement en ligne</h2>
    <p class="feature-desc">Encaissez directement sur votre propre site ou application. Vos clients paient par carte, Apple Pay ou Google Pay, en toute confiance — l'ensemble du parcours de paiement est traité et sécurisé par l'infrastructure Stripe, pendant que vous gardez le contrôle total de l'expérience d'achat.</p>
    <ul class="fc-list">
      <li>Checkout intégrable à votre site existant</li>
      <li>Expérience fluide, pensée pour convertir</li>
      <li>Aucune donnée bancaire qui transite ou ne reste chez Xepay</li>
    </ul>
  </div>
</section>

<section id="liens-de-paiement" class="feature-block alt reveal">
  <div class="feature-inner">
    <div class="feature-icon">🔗</div>
    <div class="section-tag">Paiements</div>
    <h2>Liens de paiement</h2>
    <p class="feature-desc">Pas de site web ? Pas besoin. Créez un lien en 30 secondes et partagez-le où vous voulez — WhatsApp, email, réseaux sociaux. Votre client clique, paie, et vous encaissez instantanément en XOF, USD ou EUR, sans qu'il ait besoin d'un compte ni d'une application.</p>
    <ul class="fc-list">
      <li>Montant fixe ou libre, selon votre usage</li>
      <li>Expiration configurable — 24h, 72h, ou sans limite</li>
      <li>Suivi du statut en temps réel : en attente · payé · expiré</li>
      <li>Copie et partage du lien en un clic</li>
    </ul>
  </div>
</section>

<section id="mode-de-paiement" class="feature-block reveal">
  <div class="feature-inner">
    <div class="feature-icon">💳</div>
    <div class="section-tag">Paiements</div>
    <h2>Mode de paiement</h2>
    <p class="feature-desc">Chaque client a ses habitudes. Xepay s'y adapte : carte bancaire classique, Apple Pay, Google Pay, et davantage à venir — pour que personne n'abandonne son paiement simplement parce que son mode préféré n'était pas disponible.</p>
  </div>
</section>

<section id="multi-devises" class="feature-block alt reveal">
  <div class="feature-inner">
    <div class="feature-icon">🌍</div>
    <div class="section-tag">UEMOA</div>
    <h2>Multi-devises</h2>
    <p class="feature-desc">Conçu en priorité pour la zone franc CFA. Encaissez en XOF, USD ou EUR selon le besoin de votre client ou de votre partenaire — une seule plateforme, trois devises, huit pays.</p>
    <div class="country-grid">
      <div class="country-item"><span class="country-flag">🇸🇳</span><div class="country-name">SÉNÉGAL</div></div>
      <div class="country-item"><span class="country-flag">🇨🇮</span><div class="country-name">CÔTE D'IVOIRE</div></div>
      <div class="country-item"><span class="country-flag">🇧🇯</span><div class="country-name">BÉNIN</div></div>
      <div class="country-item"><span class="country-flag">🇧🇫</span><div class="country-name">BURKINA</div></div>
      <div class="country-item"><span class="country-flag">🇲🇱</span><div class="country-name">MALI</div></div>
      <div class="country-item"><span class="country-flag">🇳🇪</span><div class="country-name">NIGER</div></div>
      <div class="country-item"><span class="country-flag">🇹🇬</span><div class="country-name">TOGO</div></div>
      <div class="country-item"><span class="country-flag">🇬🇼</span><div class="country-name">GUINÉE-B.</div></div>
    </div>
  </div>
</section>

<section id="abonnements-factures" class="feature-block reveal">
  <div class="feature-inner">
    <div class="feature-icon">🧾</div>
    <div class="section-tag">Revenu récurrent</div>
    <h2>Abonnements &amp; factures</h2>
    <p class="feature-desc">Si votre activité repose sur des paiements récurrents ou sur facturation, Xepay s'en occupe pour vous : créez des abonnements pour vos propres clients et laissez la plateforme gérer les prélèvements à échéance, ou émettez des factures ponctuelles — sans tableur, sans relance manuelle.</p>
    <ul class="fc-list">
      <li>Abonnements récurrents pour vos clients, à votre rythme</li>
      <li>Facturation ponctuelle en quelques clics</li>
      <li>Relances et échéances suivies automatiquement</li>
    </ul>
  </div>
</section>

<section id="rapports-financiers" class="feature-block alt reveal">
  <div class="feature-inner">
    <div class="feature-icon">📊</div>
    <div class="section-tag">Pilotage</div>
    <h2>Rapports financiers</h2>
    <p class="feature-desc">Votre activité méritait mieux qu'un export brut. Générez des rapports clairs de vos encaissements, filtrables par période ou par devise, prêts à partager avec votre comptable ou vos associés — sans reconstruction manuelle à chaque fin de mois.</p>
  </div>
</section>

<section id="solde-retraits" class="feature-block reveal">
  <div class="feature-inner">
    <div class="feature-icon">🏦</div>
    <div class="section-tag">Trésorerie</div>
    <h2>Solde &amp; retraits</h2>
    <p class="feature-desc">Votre solde disponible, votre solde en attente, et un seul bouton pour retirer — "Retirer des fonds" déclenche un virement vers la destination de votre choix. Vous gardez la main sur chaque retrait, que vous pouvez annuler tant qu'il n'est pas finalisé.</p>
    <ul class="fc-list">
      <li>Retrait local vers votre banque en zone UEMOA, via notre partenaire agréé Verto</li>
      <li>Ou retrait vers un compte bancaire US/EU, si vous en disposez déjà</li>
      <li>Historique complet de chaque retrait, quelle que soit la destination</li>
    </ul>
  </div>
</section>

<section id="transactions-en-direct" class="feature-block alt reveal">
  <div class="feature-inner">
    <div class="feature-icon">⚡</div>
    <div class="section-tag">Suivi</div>
    <h2>Transactions en direct</h2>
    <p class="feature-desc">Chaque paiement entrant apparaît en temps réel sur votre dashboard — filtrez par devise, statut ou date, et retrouvez l'historique complet quand vous en avez besoin. Vous êtes aussi notifié par email dès qu'un paiement arrive, qu'un lien est sur le point d'expirer, ou qu'un retrait est traité — sans avoir à garder l'œil sur l'écran en permanence.</p>
  </div>
</section>

<section id="equipe-roles" class="feature-block reveal">
  <div class="feature-inner">
    <div class="feature-icon">👥</div>
    <div class="section-tag">Business</div>
    <h2>Équipe &amp; rôles</h2>
    <p class="feature-desc">Votre activité grandit, votre équipe aussi. Invitez vos collaborateurs avec des rôles distincts et des permissions définies précisément — qui peut voir les paiements, qui peut déclencher un retrait, qui n'a accès qu'en lecture — sans jamais partager vos identifiants personnels.</p>
    <ul class="fc-list">
      <li>Rôles Propriétaire, Admin et Lecture, personnalisables sur le plan Business</li>
      <li>Permissions granulaires par capacité, pas tout ou rien</li>
      <li>Chaque membre garde ses propres identifiants</li>
    </ul>
  </div>
</section>

<section class="cta-section reveal">
  <div class="cta-inner">
    <h2>Lancez-vous <mark>sans frais initiaux</mark>.</h2>
    <p>Démarrez gratuitement avec le plan Free. Upgradez quand votre business grandit. Aucune carte bancaire requise pour commencer.</p>
    <div class="cta-actions">
      <a href="/signup" class="btn-primary">Créer un compte gratuit</a>
      <a href="/tarif" class="btn-ghost">Voir les tarifs →</a>
    </div>
  </div>
</section>
`;
}
