export const title = "Xepay — Presse";

export function render() {
  return `
<section class="page-hero reveal">
  <div class="eyebrow">Presse</div>
  <h1>Kit presse <mark>Xepay</mark>.</h1>
  <p>Vous préparez un article, un reportage ou une mention sur Xepay ? Voici de quoi nous présenter correctement.</p>
</section>

<div class="feat-grid">
  <div class="feat-card span2 reveal">
    <div class="section-tag">Boilerplate — à copier/coller</div>
    <h3>Présentation standard de Xepay</h3>
    <p class="fc-sub">Xepay est une plateforme fintech SaaS qui permet aux entrepreneurs et entreprises de la zone UEMOA (Afrique de l'Ouest) d'encaisser des paiements internationaux en XOF, USD et EUR. Construite sur l'infrastructure Stripe Connect, Xepay donne à chaque marchand son propre compte de paiement individuel, ses liens de paiement, sa facturation et son suivi financier — sans jamais détenir elle-même les fonds de ses utilisateurs. La plateforme est développée et exploitée par Alasdia Technologies LLC.</p>
  </div>

  <div class="feat-card reveal">
    <div class="section-tag">Le problème qu'on résout</div>
    <h3>Pourquoi Xepay existe</h3>
    <p class="fc-sub">Faire atterrir l'argent d'un paiement international sur un compte bancaire local en UEMOA demande normalement d'assembler soi-même plusieurs maillons : encaisser via Stripe Connect, faire sortir ces fonds en USD vers un partenaire bancaire capable de les recevoir pour le compte du marchand, puis déclencher le virement final vers la banque locale (IBAN UEMOA). Chaque maillon a ses propres règles de vérification et ne communique pas avec les autres par défaut. Xepay automatise ce parcours de bout en bout — de l'encaissement Stripe Connect au virement UEMOA via notre partenaire bancaire agréé Verto — pour que le marchand n'ait qu'un bouton "Retirer des fonds" à presser, plutôt qu'un flux à reconstruire lui-même.</p>
  </div>

  <div class="feat-card reveal">
    <div class="section-tag">Modèle</div>
    <h3>Zéro détention de fonds</h3>
    <p class="fc-sub">Chaque marchand dispose de son propre compte Stripe Connect individuel. Xepay ne transite jamais les fonds par un compte qu'elle détiendrait elle-même — elle se concentre sur les outils de pilotage, pas sur la garde des fonds.</p>
  </div>

  <div class="feat-card reveal">
    <div class="section-tag">Qui nous sommes</div>
    <h3>Alasdia Technologies LLC</h3>
    <p class="fc-sub">Xepay est développée et exploitée par Alasdia Technologies LLC, société basée à Cheyenne (Wyoming, États-Unis). Une équipe restreinte, concentrée sur un seul objectif : rendre les paiements internationaux aussi simples pour un marchand ouest-africain que pour n'importe qui d'autre dans le monde.</p>
  </div>

  <div class="feat-card reveal">
    <div class="section-tag">Contact presse</div>
    <h3>Parlons-en</h3>
    <p class="fc-sub">Pour toute demande presse, interview ou vérification d'information, écrivez-nous directement — nous répondons personnellement.</p>
    <a href="mailto:support@alasdia.com" class="plan-cta primary" style="margin-top:12px;display:inline-block;">support@alasdia.com</a>
  </div>
</div>

<div class="disclaimer-strip reveal">
  <div>🖼️</div>
  <div><strong>Logo et assets visuels.</strong> Pas encore de kit téléchargeable en ligne — écrivez-nous et nous vous envoyons directement les fichiers dont vous avez besoin (logo, couleurs de marque).</div>
</div>
`;
}
