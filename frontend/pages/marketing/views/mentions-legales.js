export const title = "Xepay — Mentions légales";

export function render() {
  return `
<section class="page-hero reveal">
  <div class="eyebrow">Informations légales</div>
  <h1>Mentions <mark>légales</mark>.</h1>
</section>

<div class="prose-section reveal">
  <div class="prose-updated">Dernière mise à jour : [à compléter]</div>

  <h2>Éditeur du site</h2>
  <p>Le site xepay.finance et la plateforme Xepay sont édités par <strong>Alasdia Technologies LLC</strong>.</p>
  <ul>
    <li>Forme juridique : [à compléter]</li>
    <li>Siège social : [à compléter]</li>
    <li>Numéro d'immatriculation : [à compléter]</li>
    <li>Contact : <a href="mailto:support@alasdia.com">support@alasdia.com</a></li>
  </ul>

  <h2>Hébergement</h2>
  <p>Le site est hébergé par [à compléter — ex. Amazon Web Services (AWS), adresse du fournisseur].</p>

  <h2>Propriété intellectuelle</h2>
  <p>L'ensemble des contenus présents sur ce site (textes, logos, visuels, nom "Xepay") est la propriété d'Alasdia Technologies LLC, sauf mention contraire. Toute reproduction sans autorisation préalable est interdite.</p>

  <h2>Traitement des paiements</h2>
  <p>Les paiements effectués via Xepay sont traités par Stripe, Inc., certifié PCI DSS. Xepay ne détient, ne stocke et ne traite directement aucune donnée de carte bancaire.</p>

  <h2>Contact</h2>
  <p>Pour toute question relative à ces mentions légales, écrivez à <a href="mailto:support@alasdia.com">support@alasdia.com</a>.</p>
</div>
`;
}
