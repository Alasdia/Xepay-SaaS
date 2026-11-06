export const title = "Xepay — À propos";

export function render() {
  return `
<section class="page-hero reveal">
  <div class="eyebrow">Notre mission</div>
  <h1>Né en Afrique de l'Ouest, <mark>pensé pour le monde</mark>.</h1>
  <p>Xepay existe pour une raison simple : permettre à n'importe quel entrepreneur de la zone UEMOA d'encaisser des paiements internationaux aussi facilement qu'ailleurs — sans détour, sans friction.</p>
</section>

<div class="feat-grid">
  <div class="feat-card span2 reveal">
    <div class="section-tag">Pourquoi Xepay</div>
    <h3>Le constat de départ</h3>
    <p class="fc-sub">Encaisser un paiement en ligne depuis Dakar, Abidjan ou Cotonou reste souvent plus compliqué que ça ne devrait l'être — comptes bancaires difficiles à obtenir, outils pensés pour d'autres marchés, démarches qui s'accumulent. Xepay est né pour combler cet écart : une couche de gestion simple, posée sur une infrastructure de paiement internationale reconnue, pour que la complexité technique et réglementaire ne soit plus votre problème.</p>
  </div>

  <div class="feat-card reveal">
    <div class="section-tag">Notre approche</div>
    <h3>Zéro détention de fonds</h3>
    <p class="fc-sub">Xepay ne détient jamais vos fonds. Chaque marchand dispose de son propre compte Stripe Connect individuel — Xepay se concentre sur ce qu'il fait de mieux : vous donner les outils pour piloter, automatiser et comprendre votre activité.</p>
  </div>

  <div class="feat-card reveal">
    <div class="section-tag">Qui nous sommes</div>
    <h3>Alasdia Technologies LLC</h3>
    <p class="fc-sub">Xepay est développé et exploité par Alasdia Technologies LLC. Une équipe restreinte, concentrée sur un seul objectif : rendre les paiements internationaux aussi simples pour un marchand ouest-africain que pour n'importe qui d'autre dans le monde.</p>
  </div>
</div>

<section class="cta-section reveal">
  <div class="cta-inner">
    <h2>Construisons <mark>ensemble</mark>.</h2>
    <p>Une question, une suggestion, une envie de collaborer ? Écrivez-nous.</p>
    <div class="cta-actions">
      <a href="mailto:support@alasdia.com" class="btn-primary">support@alasdia.com</a>
      <a href="/fonctionnalite" class="btn-ghost">Voir les fonctionnalités →</a>
    </div>
  </div>
</section>
`;
}
