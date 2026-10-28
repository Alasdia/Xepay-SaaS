export const title = "Xepay — Tarifs";

export function render() {
  return `
<section class="page-hero reveal">
  <div class="eyebrow">Tarifs transparents</div>
  <h1>Simple. <mark>Transparent</mark>.</h1>
  <p>Une commission unique sur les paiements réussis. Des plans SaaS pour centraliser, piloter et automatiser vos opérations.</p>
</section>

<div class="arch-flow reveal">
  <div class="arch-node"><div class="arch-icon">🏪</div><div class="arch-name">MARCHAND</div><div class="arch-desc">Vous — votre business, vos clients</div></div>
  <div class="arch-arrow">→</div>
  <div class="arch-node highlight"><div class="arch-icon">⚡</div><div class="arch-name">XEPAY</div><div class="arch-desc">Dashboard · Liens · Commerce · Webhooks</div></div>
  <div class="arch-arrow">→</div>
  <div class="arch-node"><div class="arch-icon">🔷</div><div class="arch-name">STRIPE CONNECT</div><div class="arch-desc">Votre compte individuel — fonds non détenus par Xepay</div></div>
  <div class="arch-arrow">→</div>
  <div class="arch-node"><div class="arch-icon">🌍</div><div class="arch-name">PAIEMENTS</div><div class="arch-desc">USD · EUR · XOF · 140+ pays</div></div>
</div>

<div class="disclaimer-strip reveal">
  <div>ℹ️</div>
  <div><strong>Xepay n'est pas une banque et ne détient aucun fonds.</strong>Chaque marchand dispose de son propre compte Stripe Connect. Xepay est une couche SaaS qui centralise la gestion, le monitoring et l'automatisation de vos opérations — les paiements sont intégralement traités et sécurisés par Stripe.</div>
</div>

<section class="commission-section reveal">
  <div class="commission-card">
    <div class="comm-rate">6% → 3%</div>
    <div class="comm-rate-label">Commission dégressive selon votre volume</div>
    <h3>Plus vous encaissez, <mark>moins vous payez</mark>.</h3>
    <p>Votre commission baisse automatiquement avec votre volume encaissé chaque mois — 6% pour démarrer, jusqu'à 3% sur les plus gros volumes. Elle couvre l'intégralité des frais (Stripe Connect inclus). Vous ne payez que lorsqu'un paiement est encaissé.</p>
    <div class="comm-breakdown">
      <div class="cb-row"><div class="cb-dot" style="background:#6366f1"></div><div class="cb-label">0 – 5 000 $ encaissés / mois</div><div class="cb-value" style="color:#6366f1">6%</div></div>
      <div class="cb-row"><div class="cb-dot" style="background:var(--gold)"></div><div class="cb-label">5 000 – 20 000 $ / mois</div><div class="cb-value" style="color:var(--gold-deep)">5%</div></div>
      <div class="cb-row"><div class="cb-dot" style="background:#f59e0b"></div><div class="cb-label">20 000 – 75 000 $ / mois</div><div class="cb-value" style="color:#b45309">4%</div></div>
      <div class="cb-row" style="border-bottom:none"><div class="cb-dot" style="background:var(--green)"></div><div class="cb-label">75 000 $+ / mois</div><div class="cb-value" style="color:var(--green)">3%</div></div>
    </div>
    <p style="font-size:12px;">Palier par palier, comme une tranche d'impôt : seul le montant au-dessus d'un seuil profite du taux inférieur — jamais de recalcul rétroactif sur ce qui est déjà encaissé.</p>
  </div>
</section>

<section class="plans-section reveal">
  <div class="plans-header">
    <div class="section-tag">Abonnements SaaS</div>
    <h2>Choisissez votre plan de gestion</h2>
    <p>La commission dégressive (6% à 3% selon votre volume, voir ci-dessus) s'applique à tous les plans. L'abonnement détermine vos outils de gestion et vos limites opérationnelles.</p>
  </div>
  <div class="plans-grid">
    <div class="plan-card">
      <div class="plan-name">Free</div>
      <div class="plan-price"><span class="amount">0</span><span class="period">XOF / mois</span></div>
      <div class="plan-price-note">+ 6% à 3% selon volume</div>
      <ul class="plan-features">
        <li><span class="pf-check">✓</span>Liens de paiement — jusqu'à 10 actifs</li>
        <li><span class="pf-check">✓</span>Dashboard temps réel</li>
        <li><span class="pf-check">✓</span>Notifications email</li>
        <li class="pf-off"><span class="pf-check pf-check-off">—</span>Historique des transactions</li>
        <li class="pf-off"><span class="pf-check pf-check-off">—</span>Webhooks & export CSV</li>
        <li class="pf-off"><span class="pf-check pf-check-off">—</span>Multi-utilisateurs</li>
      </ul>
      <a href="/signup" class="plan-cta ghost">Commencer gratuitement</a>
    </div>
    <div class="plan-card pro">
      <div class="plan-pro-badge">POPULAIRE</div>
      <div class="plan-name">Pro</div>
      <div class="plan-price"><span class="amount">15 500</span><span class="period">XOF / mois</span></div>
      <div class="plan-price-note">+ 6% à 3% selon volume</div>
      <ul class="plan-features">
        <li><span class="pf-check">✓</span>Liens de paiement — jusqu'à 100 actifs</li>
        <li><span class="pf-check">✓</span>Historique complet des transactions</li>
        <li><span class="pf-check">✓</span>Statistiques avancées & export CSV</li>
        <li><span class="pf-check">✓</span>Webhooks pour vos intégrations</li>
        <li class="pf-off"><span class="pf-check pf-check-off">—</span>Multi-utilisateurs</li>
      </ul>
      <a href="/signup" class="plan-cta primary">Passer au Pro →</a>
    </div>
    <div class="plan-card">
      <div class="plan-name">Business</div>
      <div class="plan-price"><span class="amount">36 000</span><span class="period">XOF / mois</span></div>
      <div class="plan-price-note">+ 6% à 3% selon volume</div>
      <ul class="plan-features">
        <li><span class="pf-check">✓</span>Liens de paiement illimités</li>
        <li><span class="pf-check">✓</span>Tout le plan Pro inclus</li>
        <li><span class="pf-check">✓</span>Multi-utilisateurs & rôles</li>
        <li><span class="pf-check">✓</span>Volumes élevés, support prioritaire</li>
        <li><span class="pf-check">✓</span>KYB entreprise accompagné</li>
      </ul>
      <a href="/signup" class="plan-cta ghost">Choisir Business →</a>
    </div>
  </div>
</section>

<section class="compare-section reveal">
  <table class="compare-table">
    <thead><tr><th>Fonctionnalité</th><th>Free</th><th>Pro</th><th>Business</th></tr></thead>
    <tbody>
      <tr class="cat-row"><td colspan="4">Paiements</td></tr>
      <tr><td>Commission par paiement</td><td>6% → 3%</td><td>6% → 3%</td><td>6% → 3%</td></tr>
      <tr><td>Liens de paiement actifs</td><td>10 max</td><td>100 max</td><td>Illimité</td></tr>
      <tr><td>Devises (XOF, USD, EUR)</td><td class="yes">✓</td><td class="yes">✓</td><td class="yes">✓</td></tr>
      <tr class="cat-row"><td colspan="4">Dashboard & monitoring</td></tr>
      <tr><td>Historique des transactions</td><td class="no">—</td><td class="yes">✓</td><td class="yes">✓</td></tr>
      <tr><td>Statistiques avancées & export CSV</td><td class="no">—</td><td class="yes">✓</td><td class="yes">✓</td></tr>
      <tr><td>Webhooks</td><td class="no">—</td><td class="yes">✓</td><td class="yes">✓</td></tr>
      <tr class="cat-row"><td colspan="4">Équipe & sécurité</td></tr>
      <tr><td>Multi-utilisateurs & rôles</td><td class="no">—</td><td class="no">—</td><td class="yes">✓</td></tr>
      <tr><td>Support prioritaire</td><td class="no">—</td><td class="no">—</td><td class="yes">✓</td></tr>
    </tbody>
  </table>
</section>

<section class="faq-section reveal">
  <div class="section-tag">FAQ</div>
  <details class="faq-item" open>
    <summary>Est-ce que Xepay détient mes fonds ?</summary>
    <p>Non. Xepay ne détient aucun fonds. Chaque marchand dispose de son propre compte Stripe Connect. Les paiements sont traités et conservés par Stripe directement. Xepay intervient uniquement comme couche de gestion et d'automatisation au-dessus de Stripe.</p>
  </details>
  <details class="faq-item">
    <summary>Que couvre la commission, et pourquoi baisse-t-elle ?</summary>
    <p>Elle couvre l'intégralité des frais : frais Stripe Connect, l'application fee Xepay, ainsi que la marge opérationnelle. Elle commence à 6% puis baisse automatiquement avec votre volume encaissé chaque mois, palier par palier comme une tranche d'impôt.</p>
  </details>
  <details class="faq-item">
    <summary>Dois-je payer l'abonnement ET la commission ?</summary>
    <p>Oui, les deux sont indépendants. L'abonnement SaaS détermine vos outils de gestion et vos limites. La commission s'applique à chaque paiement réussi, quel que soit votre plan. Le plan Free est gratuit — vous ne payez que la commission.</p>
  </details>
  <details class="faq-item">
    <summary>Qu'est-ce qu'un compte Stripe Connect ?</summary>
    <p>Stripe Connect est l'infrastructure de paiement de Stripe dédiée aux plateformes. Chaque marchand Xepay possède son propre compte Stripe Connect individuel, certifié PCI DSS, capable de recevoir des paiements dans 140+ pays en USD, EUR, XOF.</p>
  </details>
  <details class="faq-item">
    <summary>Puis-je changer de plan à tout moment ?</summary>
    <p>Oui. Vous pouvez upgrader ou downgrader votre plan à tout moment depuis votre dashboard. Le changement prend effet immédiatement. Aucun engagement minimum, aucune pénalité.</p>
  </details>
</section>

<section class="cta-section reveal">
  <div class="cta-inner">
    <h2>Démarrez <mark>sans risque</mark>.</h2>
    <p>Le plan Free est gratuit. Aucune carte bancaire requise. Vous ne payez que lorsque vous encaissez.</p>
    <div class="cta-actions">
      <a href="/signup" class="btn-primary">Créer un compte gratuit</a>
      <a href="/fonctionnalite" class="btn-ghost">Voir les fonctionnalités →</a>
    </div>
  </div>
</section>
`;
}
