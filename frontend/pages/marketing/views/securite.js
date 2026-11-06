export const title = "Xepay — Sécurité";

export function render() {
  return `
<section class="page-hero reveal">
  <div class="eyebrow">Sécurité</div>
  <h1>Protéger vos <mark>paiements et vos données</mark>.</h1>
  <p>La sécurité n'est pas une option chez Xepay — c'est la base sur laquelle tout le reste est construit.</p>
</section>

<div class="feat-grid">
  <div class="feat-card reveal">
    <div class="section-tag">Paiements</div>
    <h3>Infrastructure Stripe</h3>
    <p class="fc-sub">Vos paiements sont traités et sécurisés par Stripe, certifié PCI DSS niveau 1 — le plus haut standard de sécurité de l'industrie des paiements. Xepay ne stocke jamais vos numéros de carte.</p>
  </div>
  <div class="feat-card reveal">
    <div class="section-tag">Zéro détention</div>
    <h3>Vos fonds restent les vôtres</h3>
    <p class="fc-sub">Chaque marchand dispose de son propre compte Stripe Connect. Xepay ne détient, ne touche et ne peut jamais déplacer vos fonds — ils transitent directement entre vos clients et votre compte.</p>
  </div>
  <div class="feat-card reveal">
    <div class="section-tag">Accès au compte</div>
    <h3>Authentification renforcée</h3>
    <p class="fc-sub">Double authentification (2FA) par application, codes de secours, et support des clés de sécurité physiques (passkeys) — à activer à tout moment depuis vos paramètres.</p>
  </div>
  <div class="feat-card reveal">
    <div class="section-tag">Traçabilité</div>
    <h3>Journal de sécurité</h3>
    <p class="fc-sub">Chaque connexion et action sensible sur votre compte est enregistrée et consultable, avec une alerte email en cas de connexion depuis un nouvel appareil.</p>
  </div>
  <div class="feat-card reveal">
    <div class="section-tag">Intégrations</div>
    <h3>Webhooks vérifiés</h3>
    <p class="fc-sub">Chaque webhook envoyé par Xepay est signé — vous pouvez vérifier cryptographiquement qu'il provient bien de nous avant de l'accepter dans vos systèmes.</p>
  </div>
  <div class="feat-card reveal">
    <div class="section-tag">Équipe & rôles</div>
    <h3>Permissions granulaires</h3>
    <p class="fc-sub">Sur le plan Business, définissez précisément qui, dans votre équipe, peut voir les paiements, déclencher un retrait ou gérer la configuration — rien par défaut, tout est explicite.</p>
  </div>
</div>

<div class="disclaimer-strip reveal">
  <div>🔒</div>
  <div><strong>Une faille à signaler ?</strong> Écrivez-nous directement à <a href="mailto:support@alasdia.com">support@alasdia.com</a> — nous traitons chaque signalement avec sérieux et rapidité.</div>
</div>
`;
}
