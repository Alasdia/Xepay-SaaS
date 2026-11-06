export const title = "Xepay — Cookies";

export function render() {
  return `
<section class="page-hero reveal">
  <div class="eyebrow">Politique de cookies</div>
  <h1>Comment nous utilisons les <mark>cookies</mark>.</h1>
</section>

<div class="prose-section reveal">
  <div class="prose-updated">Dernière mise à jour : [à compléter]</div>

  <h2>Ce que nous utilisons</h2>
  <p>Xepay utilise uniquement des cookies strictement nécessaires au fonctionnement du service — notamment un cookie de session qui vous garde connecté à votre compte après une connexion réussie. Ce cookie est indispensable : sans lui, vous ne pourriez pas rester connecté au dashboard.</p>

  <h2>Ce que nous n'utilisons pas</h2>
  <p>À ce jour, Xepay n'utilise aucun cookie publicitaire ni aucun outil d'analyse ou de suivi tiers (type Google Analytics) sur ses pages publiques. Si cela venait à changer, cette page serait mise à jour en conséquence, avec un recueil de votre consentement lorsque requis.</p>

  <h2>Cookies tiers</h2>
  <p>Certaines actions (comme le paiement lui-même) peuvent impliquer des cookies posés directement par Stripe, notre prestataire de traitement des paiements, dans le cadre de la sécurisation de la transaction. Ces cookies relèvent de la politique de confidentialité de Stripe.</p>

  <h2>Gérer les cookies</h2>
  <p>Le cookie de session Xepay étant strictement nécessaire, il n'existe pas d'option pour le désactiver tout en restant connecté. Vous pouvez à tout moment le supprimer via les paramètres de votre navigateur — vous serez alors simplement déconnecté.</p>

  <h2>Contact</h2>
  <p>Pour toute question sur notre usage des cookies, écrivez à <a href="mailto:support@alasdia.com">support@alasdia.com</a>.</p>
</div>
`;
}
