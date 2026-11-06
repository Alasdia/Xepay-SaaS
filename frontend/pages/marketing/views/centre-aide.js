export const title = "Xepay — Centre d'aide";

export function render() {
  return `
<section class="page-hero reveal">
  <div class="eyebrow">Centre d'aide</div>
  <h1>Comment pouvons-nous <mark>vous aider</mark> ?</h1>
  <p>Les réponses aux questions les plus courantes — et un contact direct si vous n'y trouvez pas la vôtre.</p>
</section>

<section class="faq-section reveal">
  <div class="section-tag">Démarrage</div>
  <details class="faq-item" open>
    <summary>Comment créer mon compte Xepay ?</summary>
    <p>Cliquez sur "Créer un compte", renseignez votre email et créez votre mot de passe. Vous accédez immédiatement à votre dashboard — l'activation des paiements se fait ensuite en configurant votre compte Stripe Connect depuis votre profil.</p>
  </details>
  <details class="faq-item">
    <summary>Pourquoi dois-je configurer un compte Stripe Connect ?</summary>
    <p>Stripe Connect est l'infrastructure qui traite et sécurise réellement vos paiements. Xepay ne détient aucun fonds : chaque marchand a son propre compte Stripe Connect individuel, et Xepay se positionne comme la couche de gestion au-dessus.</p>
  </details>
  <details class="faq-item">
    <summary>Combien de temps prend l'activation de mon compte ?</summary>
    <p>La création du compte Stripe Connect est immédiate. La vérification complète (KYC) dépend des informations fournies et prend généralement de quelques minutes à quelques jours.</p>
  </details>

  <div class="section-tag" style="margin-top:32px;">Paiements & retraits</div>
  <details class="faq-item">
    <summary>Dans quelles devises puis-je encaisser ?</summary>
    <p>XOF, USD et EUR, selon le besoin de votre client — voir la page Fonctionnalités pour le détail par pays.</p>
  </details>
  <details class="faq-item">
    <summary>Comment retirer mes fonds ?</summary>
    <p>Depuis la vue Solde de votre dashboard, le bouton "Retirer des fonds" déclenche un virement Stripe vers le compte bancaire enregistré sur votre compte Connect. Voir la section "Retraits & Comptes US" de vos paramètres pour les détails de couverture actuelle.</p>
  </details>
  <details class="faq-item">
    <summary>Quelle commission Xepay applique-t-elle ?</summary>
    <p>Une commission dégressive de 6% à 3% selon votre volume mensuel encaissé — voir la page Tarifs pour le barème complet.</p>
  </details>

  <div class="section-tag" style="margin-top:32px;">Compte & sécurité</div>
  <details class="faq-item">
    <summary>Puis-je ajouter des membres à mon équipe ?</summary>
    <p>Oui, à partir du plan Business, avec des rôles et permissions configurables depuis vos paramètres.</p>
  </details>
  <details class="faq-item">
    <summary>Comment activer la double authentification (2FA) ?</summary>
    <p>Depuis Paramètres → Authentification, vous pouvez activer la 2FA par application ou enregistrer une clé de sécurité (passkey).</p>
  </details>
</section>

<div class="disclaimer-strip reveal">
  <div>💬</div>
  <div><strong>Votre question n'est pas listée ?</strong> Écrivez-nous à <a href="mailto:support@alasdia.com">support@alasdia.com</a>, nous répondons personnellement.</div>
</div>
`;
}
