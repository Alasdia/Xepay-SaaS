export const title = "Xepay — Mentions légales";

export function render() {
  return `
<section class="page-hero reveal">
  <div class="eyebrow">Informations légales</div>
  <h1>Mentions <mark>légales</mark>.</h1>
</section>

<div class="prose-section reveal">
  <div class="prose-updated">Dernière mise à jour : 13 novembre 2026</div>

  <h2>Éditeur du site</h2>
  <p>Le site xepay.finance et la plateforme Xepay sont édités par <strong>Alasdia Technologies LLC</strong>.</p>
  <ul>
    <li>Forme juridique : Limited Liability Company (LLC)</li>
    <li>Siège social : 1021 E Lincolnway, Ste 10459, Cheyenne, WY 82001, États-Unis</li>
    <li>Numéro d'immatriculation : 2026-002005229 (Wyoming Secretary of State)</li>
    <li>Contact : <a href="mailto:support@alasdia.com">support@alasdia.com</a></li>
  </ul>

  <h2>Hébergement</h2>
  <p>Les pages web du site sont hébergées par Vercel Inc. Le serveur applicatif (backend) et la base de données sont hébergés sur Amazon Web Services (AWS), via une instance EC2.</p>

  <h2>Propriété intellectuelle</h2>
  <p>L'ensemble des contenus présents sur ce site (textes, logos, visuels, nom "Xepay") est la propriété d'Alasdia Technologies LLC, sauf mention contraire. Toute reproduction sans autorisation préalable est interdite.</p>

  <h2>Traitement des paiements</h2>
  <p>Les paiements effectués via Xepay sont traités par Stripe, Inc., certifié PCI DSS. Xepay ne détient, ne stocke et ne traite directement aucune donnée de carte bancaire.</p>

  <h2>Contact</h2>
  <p>Pour toute question relative à ces mentions légales, écrivez à <a href="mailto:support@alasdia.com">support@alasdia.com</a>.</p>
</div>
`;
}
