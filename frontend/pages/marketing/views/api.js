export const title = "Xepay — API";

export function render() {
  return `
<section class="page-hero reveal">
  <div class="eyebrow">API & Webhooks</div>
  <h1>Intégrez Xepay <mark>à vos outils</mark>.</h1>
  <p>Clés API et webhooks pour connecter Xepay à votre site, votre application ou vos systèmes internes.</p>
</section>

<div class="feat-grid">
  <div class="feat-card reveal">
    <div class="section-tag">Authentification</div>
    <h3>Clés API</h3>
    <p class="fc-sub">Générez vos clés API directement depuis votre dashboard, dans Paramètres. Chaque clé est liée à votre compte et peut être révoquée à tout moment.</p>
  </div>
  <div class="feat-card reveal">
    <div class="section-tag">Temps réel</div>
    <h3>Webhooks</h3>
    <p class="fc-sub">Enregistrez une URL de webhook pour recevoir en temps réel les événements qui comptent — paiement réussi, retrait traité, et plus — plutôt que d'interroger l'API en continu.</p>
  </div>
  <div class="feat-card reveal">
    <div class="section-tag">Disponibilité</div>
    <h3>Statut de l'API</h3>
    <p class="fc-sub">L'API Xepay suit la même disponibilité que le reste de la plateforme. Voir la page Statut pour toute information en cas d'incident.</p>
  </div>
</div>

<div class="disclaimer-strip reveal">
  <div>🛠️</div>
  <div><strong>Référence API détaillée à venir.</strong> Besoin d'intégrer Xepay dès maintenant ? Écrivez-nous à <a href="mailto:support@alasdia.com">support@alasdia.com</a> — nous vous accompagnons directement.</div>
</div>
`;
}
