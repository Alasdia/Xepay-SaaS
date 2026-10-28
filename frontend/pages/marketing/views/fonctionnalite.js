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

<div class="feat-grid">
  <div class="feat-card span2 reveal">
    <div class="section-tag">Paiements</div>
    <h3>Liens de paiement</h3>
    <p class="fc-sub">Créez un lien en 30 secondes, partagez-le où vous voulez — WhatsApp, email, réseaux sociaux. Votre client paie sans compte, sans app. Vous encaissez instantanément en XOF, USD ou EUR.</p>
    <ul class="fc-list">
      <li>Lien avec montant fixe ou libre</li>
      <li>Expiration configurable (ex. 24h, 72h, sans limite)</li>
      <li>Suivi du statut : en attente · payé · expiré</li>
      <li>Copie du lien en un clic + partage direct</li>
    </ul>
    <div class="lnk-quota">
      <div class="lnk-quota-top"><span>Liens utilisés</span><strong>3/10</strong></div>
      <div class="lnk-quota-bar"><div class="lnk-quota-fill" style="width:30%"></div></div>
    </div>
    <div class="lnk-row lnk-pending"><span class="lnk-dot"></span><span class="lnk-url">app.xepay.finance/pay/pl_vbl0qzddig7i…</span><i class="lnk-chevron">›</i></div>
    <div class="lnk-row lnk-paid"><span class="lnk-dot"></span><span class="lnk-url">app.xepay.finance/pay/pl_qi4x1zhg3m5…</span><i class="lnk-chevron">›</i></div>
  </div>

  <div class="feat-card reveal">
    <div class="section-tag">UEMOA</div>
    <h3>XOF en premier</h3>
    <p class="fc-sub">Conçu pour la zone franc CFA. Encaissez en XOF, USD ou EUR selon le besoin de votre client ou partenaire.</p>
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

  <div class="feat-card span2 reveal">
    <div class="section-tag">Abonnements</div>
    <h3>Free · Pro · Business</h3>
    <p class="fc-sub">Démarrez gratuitement et upgradez selon votre volume. Chaque plan débloque plus de liens, les webhooks et la gestion multi-utilisateurs.</p>
    <div class="plan-mini-row">
      <div class="plan-mini-left"><div class="plan-mini-icon">🆓</div><div><div class="plan-mini-name">Free</div><div class="plan-mini-desc">Pour démarrer sans engagement</div></div></div>
      <div class="plan-mini-badge">10 liens</div>
    </div>
    <div class="plan-mini-row">
      <div class="plan-mini-left"><div class="plan-mini-icon">🚀</div><div><div class="plan-mini-name">Pro</div><div class="plan-mini-desc">Pour les marchands en croissance</div></div></div>
      <div class="plan-mini-badge">100 liens · webhooks</div>
    </div>
    <div class="plan-mini-row">
      <div class="plan-mini-left"><div class="plan-mini-icon">💼</div><div><div class="plan-mini-name">Business</div><div class="plan-mini-desc">Équipes · volumes élevés</div></div></div>
      <div class="plan-mini-badge">Illimité · multi-users</div>
    </div>
  </div>

  <div class="feat-card reveal">
    <div class="section-tag">Conformité</div>
    <h3>Profil & KYC</h3>
    <p class="fc-sub">Les vérifications d'identité sont traitées via l'infrastructure sécurisée Stripe Connect pour débloquer les retraits.</p>
    <div class="kyc-step"><div class="kyc-num kyc-done">✓</div><div class="kyc-label">Informations transmises</div><div class="kyc-status" style="color:var(--green)">Validé</div></div>
    <div class="kyc-step"><div class="kyc-num kyc-done">✓</div><div class="kyc-label">Vérification d'identité</div><div class="kyc-status" style="color:var(--green)">Confirmé</div></div>
    <div class="kyc-step"><div class="kyc-num kyc-curr">→</div><div class="kyc-label">Conformité activité</div><div class="kyc-status" style="color:var(--gold-deep)">En cours</div></div>
    <div class="kyc-step"><div class="kyc-num kyc-pend">4</div><div class="kyc-label">Activation des retraits</div><div class="kyc-status" style="color:var(--muted2)">En attente</div></div>
  </div>

  <div class="feat-card reveal">
    <div class="section-tag">Analytics</div>
    <h3>Transactions en direct</h3>
    <p class="fc-sub">Visualisez chaque paiement entrant, filtrez par devise, statut ou date. Exportez pour votre comptable.</p>
    <div class="txn-kpis">
      <div class="txn-kpi active"><span>Tous</span><strong>8</strong></div>
      <div class="txn-kpi"><span>Réussis</span><strong>8</strong></div>
    </div>
    <div class="txn-table">
      <div class="txn-thead"><span>Client</span><span>Moyen</span><span>Brut</span><span>Net</span></div>
      <div class="txn-trow"><span class="txn-client">alasndia04@gmail.com</span><span class="txn-method"><span class="txn-card txn-card-mc"></span>···4444</span><span class="txn-amount">23,00 USD</span><span class="txn-net">21,62 USD</span></div>
    </div>
  </div>

  <div class="feat-card reveal">
    <div class="section-tag">Business</div>
    <h3>Multi-utilisateurs</h3>
    <p class="fc-sub">Ajoutez votre équipe avec des rôles distincts. Gérez les accès sans partager vos identifiants.</p>
    <div class="user-row"><div class="user-av">AK</div><div><div class="user-name">Amadou Koné</div><div class="user-role">Propriétaire du compte</div></div><div class="user-badge">OWNER</div></div>
    <div class="user-row"><div class="user-av">FD</div><div><div class="user-name">Fatou Diallo</div><div class="user-role">Gestion des liens & paiements</div></div><div class="user-badge">ADMIN</div></div>
    <div class="user-row"><div class="user-av">MS</div><div><div class="user-name">Moussa Sarr</div><div class="user-role">Lecture seule — rapports</div></div><div class="user-badge">LECTURE</div></div>
  </div>

  <div class="feat-card reveal">
    <div class="section-tag">Sécurité</div>
    <h3>Sécurité maximale</h3>
    <p class="fc-sub">Chaque transaction est protégée. Votre argent ne bouge que si vous l'avez autorisé.</p>
    <div class="sec-row"><div class="sec-ic">🔒</div><div><div class="sec-title">Double authentification & passkeys</div><div class="sec-desc">Protection avancée des accès</div></div><div class="sec-check">✓</div></div>
    <div class="sec-row"><div class="sec-ic">🤖</div><div><div class="sec-title">Protection anti-fraude</div><div class="sec-desc">Analyse automatisée via Stripe Radar</div></div><div class="sec-check">✓</div></div>
    <div class="sec-row"><div class="sec-ic">📋</div><div><div class="sec-title">KYC & conformité</div><div class="sec-desc">Vérification d'identité via Stripe Connect</div></div><div class="sec-check">✓</div></div>
  </div>

  <div class="feat-card reveal">
    <div class="section-tag">Notifications</div>
    <h3>Alertes instantanées</h3>
    <p class="fc-sub">Soyez notifié par email dès qu'un paiement est reçu, qu'un lien expire ou qu'un retrait est traité.</p>
    <div class="notif-row"><div class="notif-ic">💰</div><div><div class="notif-title">Paiement reçu</div><div class="notif-body">+390 USD de Diallo Textiles</div><div class="notif-time">Il y a 2 min · Email</div></div></div>
    <div class="notif-row"><div class="notif-ic">⏰</div><div><div class="notif-title">Lien sur le point d'expirer</div><div class="notif-body">150 000 XOF · dans 1h</div><div class="notif-time">Il y a 5 min · Email</div></div></div>
  </div>
</div>

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
