export const title = "Xepay — Statut";

export function render() {
  return `
<section class="page-hero reveal">
  <div class="eyebrow">Statut de la plateforme</div>
  <h1>Disponibilité des <mark>services Xepay</mark>.</h1>
  <p>Un tableau de bord de statut en temps réel est en préparation. En attendant, voici comment rester informé.</p>
</section>

<div class="disclaimer-strip reveal">
  <div>📡</div>
  <div><strong>Page de statut détaillée à venir.</strong> Elle affichera la disponibilité en temps réel de l'API, du dashboard et des paiements, ainsi que l'historique des incidents.</div>
</div>

<div class="feat-grid">
  <div class="feat-card reveal">
    <div class="section-tag">En cas d'incident</div>
    <h3>Comment nous vous informons</h3>
    <p class="fc-sub">Si un incident affecte les paiements ou le dashboard, notre équipe vous contacte directement par email dès que possible. Vous pouvez aussi nous écrire pour vérifier l'état d'un service précis.</p>
  </div>
  <div class="feat-card reveal">
    <div class="section-tag">Signaler un problème</div>
    <h3>Vous rencontrez un souci ?</h3>
    <p class="fc-sub">Décrivez ce que vous observez et nous vous répondons rapidement.</p>
    <a href="mailto:support@alasdia.com" class="plan-cta primary" style="margin-top:12px;display:inline-block;">support@alasdia.com</a>
  </div>
</div>
`;
}
