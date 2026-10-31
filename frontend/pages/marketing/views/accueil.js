import { mountGlobe } from "/marketing/globe.js";
import { mountGlobeBg } from "/marketing/globe-bg.js";
import { mountArchitecture } from "/marketing/architecture.js";
import { mountPayments } from "/marketing/payments.js";
import { mountTransactions } from "/marketing/transactions.js";
import { mountReports } from "/marketing/reports.js";
import { mountTeam } from "/marketing/team.js";
import { mountCheckoutDemo } from "/marketing/checkoutDemo.js";

export const title = "Xepay — Paiements fintech, de l'Afrique de l'Ouest au monde";

export function render() {
  return `
<!-- ─── HERO ─── -->
<section class="hero">
  <div class="hero-inner">
    <!-- TEXT -->
    <div class="hero-text reveal">
      <div class="hero-eyebrow">Né en Afrique de l'Ouest, connecté au monde</div>
      <h1>
        Centralisez vos flux.<br>
        <mark>Automatisez</mark> le reste.
      </h1>
      <p class="hero-desc">
        Xepay donne aux marchands ouest-africains les outils d'une
        plateforme fintech mondiale : recevez des paiements en XOF, USD
        ou EUR et connectez votre business au reste du monde.
      </p>
      <div class="hero-actions">
        <a href="/signup" class="btn-primary">Commencer gratuitement</a>
        <a href="/fonctionnalite" class="btn-ghost">▷ Voir les fonctionnalités</a>
      </div>
      <div class="hero-stats">

        <div class="hero-stat">
          <div class="label">UEMOA → Monde</div>
        </div>

        <div class="hero-stat">
          <div class="label">XOF · USD · EUR</div>
        </div>

        <div class="hero-stat">
          <div class="label">Propulsé par Stripe Connect</div>
        </div>

      </div>
    </div>

    <div class="hero-visual reveal" style="transition-delay:0.15s">
      <div class="hero-halo"></div>
    </div>
  </div>
</section>

<!-- ─── STATS BAR ─── -->
<div class="stats-bar">
  <div class="stats-inner">
    <div class="stat-item">
      <div class="stat-num">Stripe <span class="accent">Connect</span></div>
      <div class="stat-label">Infrastructure paiements</div>
    </div>

    <div class="stat-item">
      <div class="stat-num">KYC <span class="accent">Automatisé</span></div>
      <div class="stat-label">Vérification intégrée</div>
    </div>

    <div class="stat-item">
      <div class="stat-num">Exports <span class="accent">Comptables</span></div>
      <div class="stat-label">CSV / PDF</div>
    </div>

    <div class="stat-item">
      <div class="stat-num">Support <span class="accent">International</span></div>
      <div class="stat-label">Paiements globaux</div>
    </div>
  </div>

  <!-- Moyens de paiement acceptés - défilement décoratif, icônes réelles (/assets) -->
  <div class="payment-marquee" aria-hidden="true">
    <div class="payment-marquee-track">
      <span class="payment-chip"><img src="/assets/visa.svg" alt="">Visa</span>
      <span class="payment-chip"><img src="/assets/mastercard.svg" alt="">Mastercard</span>
      <span class="payment-chip"><img src="/assets/apple-pay.svg" alt="">Apple Pay</span>
      <span class="payment-chip"><img src="/assets/google-pay.svg" alt="">Google Pay</span>
      <span class="payment-chip"><img src="/assets/cashapp.svg" alt="">Cash App</span>
      <span class="payment-chip"><img src="/assets/klarna-logo.svg" alt="">Klarna</span>
      <span class="payment-chip"><img src="/assets/affirm.svg" alt="">Affirm</span>
      <span class="payment-chip"><img src="/assets/link.svg" alt="">Link</span>
      <span class="payment-chip"><img src="/assets/bancontact.svg" alt="">Bancontact</span>
      <span class="payment-chip"><img src="/assets/visa.svg" alt="">Visa</span>
      <span class="payment-chip"><img src="/assets/mastercard.svg" alt="">Mastercard</span>
      <span class="payment-chip"><img src="/assets/apple-pay.svg" alt="">Apple Pay</span>
      <span class="payment-chip"><img src="/assets/google-pay.svg" alt="">Google Pay</span>
      <span class="payment-chip"><img src="/assets/cashapp.svg" alt="">Cash App</span>
      <span class="payment-chip"><img src="/assets/klarna-logo.svg" alt="">Klarna</span>
      <span class="payment-chip"><img src="/assets/affirm.svg" alt="">Affirm</span>
      <span class="payment-chip"><img src="/assets/link.svg" alt="">Link</span>
      <span class="payment-chip"><img src="/assets/bancontact.svg" alt="">Bancontact</span>
    </div>
  </div>
</div>

<!-- ─── LIGNES LATÉRALES : du bas de la barre de paiement jusqu'à la fin du contenu de la page ─── -->
<div class="page-rails">
<!-- ─── GLOBE ─── -->
<section class="globe-section reveal">
  <canvas class="globe-bg-canvas" aria-hidden="true" data-globe-bg-canvas></canvas>
  <div class="globe-section-inner">
    <div class="globe-text">
      <h2>Le monde paie.<br>L'Afrique de l'Ouest encaisse.</h2>
      <p>Recevez des paiements en dollars, euros et XOF depuis n'importe quel pays, directement sur votre compte Xepay.</p>
    </div>
    <div class="globe-visual">
      <canvas class="globe-canvas" aria-hidden="true"></canvas>
      <div class="globe-labels" aria-hidden="true"></div>
    </div>
  </div>
</section>

<!-- ─── GRILLE : clients/paiements en bloc horizontal, 3 blocs verticaux ─── -->
<section class="grid-features-section reveal">
  <div class="gf-grid">
    <!-- Bloc horizontal : carte unique, titre en haut à gauche, grid 2 colonnes (reçu | cadre navigateur) -->
    <div class="gf-block gf-wide">
      <div class="gf-wide-card">
        <h2 class="gf-wide-title">Recevez les paiements<br>de vos clients.</h2>

        <div class="xp-payments-frame">
          <div class="xp-payments-stage">
            <div class="xp-payments-layout">
              <!-- Colonne gauche : reçu, ancré en bas -->
              <div class="xp-payments-receipt-col">
                <div class="xp-payments-receipt-backdrop" aria-hidden="true"></div>
                <div class="xp-receipt" aria-hidden="true" data-xp-receipt>
                  <div class="xp-receipt-label">Reçu de paiement</div>
                  <div class="xp-receipt-row"><span>Client</span><strong data-xp-receipt-name>Leona Bravo</strong></div>
                  <div class="xp-receipt-row"><span>N° facture</span><strong data-xp-receipt-order>#CMD-10432</strong></div>
                  <div class="xp-receipt-row"><span>Date</span><strong data-xp-receipt-date>27 oct. 2026</strong></div>
                  <div class="xp-receipt-row"><span>Moyen</span><strong><img data-xp-receipt-method-icon src="/assets/cashapp.svg" alt="Cash App"><span data-xp-receipt-method-label>Cash App</span></strong></div>
                  <div class="xp-receipt-total"><span>Total</span><strong data-xp-receipt-amount>180,00 USD</strong></div>
                </div>
              </div>

              <!-- Colonne droite : cadre tableau de bord, fond --gold rayé qui dépasse en haut/à droite -->
              <div class="xp-payments-dash-col">
                <div class="xp-payments-dash-backdrop" aria-hidden="true"></div>
                <div class="xp-dash">
                  <div class="xp-dash-bar">
                    <span class="xp-dash-dots"><span></span><span></span><span></span></span>
                    <span class="xp-dash-url">dashboard.xepay.finance</span>
                  </div>
                  <div class="xp-dash-table" aria-hidden="true" data-xp-dash-table>
                    <div class="xp-dash-thead">
                      <span>Client</span><span>Pays</span><span>Montant</span><span>Moyen</span><span>Statut</span>
                    </div>
                    <div class="xp-dash-row">
                      <span class="xp-dash-client">
                        <span class="xp-dash-avatar xp-dash-avatar-1">MN</span>
                        <span class="xp-dash-client-info">
                          <span class="xp-dash-client-name">Moussa Ndiaye</span>
                          <span class="xp-dash-client-date">28 oct. 2026</span>
                        </span>
                      </span>
                      <span class="xp-dash-country">🇺🇸 US</span>
                      <span class="xp-dash-amount">1 240,00 USD</span>
                      <span class="xp-dash-method"><img src="/assets/mastercard.svg" alt="Mastercard"></span>
                      <span class="xp-dash-status"><span class="xp-dash-status-badge xp-dash-status-badge--reussi">Réussi</span></span>
                    </div>
                    <div class="xp-dash-row">
                      <span class="xp-dash-client">
                        <span class="xp-dash-avatar xp-dash-avatar-2">LB</span>
                        <span class="xp-dash-client-info">
                          <span class="xp-dash-client-name">Leona Bravo</span>
                          <span class="xp-dash-client-date">27 oct. 2026</span>
                        </span>
                      </span>
                      <span class="xp-dash-country">🇸🇳 SN</span>
                      <span class="xp-dash-amount">180,00 USD</span>
                      <span class="xp-dash-method"><img src="/assets/cashapp.svg" alt="Cash App"></span>
                      <span class="xp-dash-status"><span class="xp-dash-status-badge xp-dash-status-badge--reussi">Réussi</span></span>
                    </div>
                    <div class="xp-dash-row">
                      <span class="xp-dash-client">
                        <span class="xp-dash-avatar xp-dash-avatar-3">ML</span>
                        <span class="xp-dash-client-info">
                          <span class="xp-dash-client-name">Malick Ly</span>
                          <span class="xp-dash-client-date">25 oct. 2026</span>
                        </span>
                      </span>
                      <span class="xp-dash-country">🇨🇮 CI</span>
                      <span class="xp-dash-amount">420,00 USD</span>
                      <span class="xp-dash-method"><img src="/assets/apple-pay.svg" alt="Apple Pay"></span>
                      <span class="xp-dash-status"><span class="xp-dash-status-badge xp-dash-status-badge--reussi">Réussi</span></span>
                    </div>
                    <div class="xp-dash-row">
                      <span class="xp-dash-client">
                        <span class="xp-dash-avatar xp-dash-avatar-1">AD</span>
                        <span class="xp-dash-client-info">
                          <span class="xp-dash-client-name">Awa Diop</span>
                          <span class="xp-dash-client-date">24 oct. 2026</span>
                        </span>
                      </span>
                      <span class="xp-dash-country">🇧🇯 BJ</span>
                      <span class="xp-dash-amount">95,00 USD</span>
                      <span class="xp-dash-method"><img src="/assets/google-pay.svg" alt="Google Pay"></span>
                      <span class="xp-dash-status"><span class="xp-dash-status-badge xp-dash-status-badge--reussi">Réussi</span></span>
                    </div>
                    <div class="xp-dash-row">
                      <span class="xp-dash-client">
                        <span class="xp-dash-avatar xp-dash-avatar-2">TB</span>
                        <span class="xp-dash-client-info">
                          <span class="xp-dash-client-name">Thierno Bah</span>
                          <span class="xp-dash-client-date">22 oct. 2026</span>
                        </span>
                      </span>
                      <span class="xp-dash-country">🇹🇬 TG</span>
                      <span class="xp-dash-amount">310,00 USD</span>
                      <span class="xp-dash-method"><img src="/assets/klarna-logo.svg" alt="Klarna"></span>
                      <span class="xp-dash-status"><span class="xp-dash-status-badge xp-dash-status-badge--conteste">Contesté</span></span>
                    </div>
                    <div class="xp-dash-row">
                      <span class="xp-dash-client">
                        <span class="xp-dash-avatar xp-dash-avatar-3">FK</span>
                        <span class="xp-dash-client-info">
                          <span class="xp-dash-client-name">Fatou Keita</span>
                          <span class="xp-dash-client-date">20 oct. 2026</span>
                        </span>
                      </span>
                      <span class="xp-dash-country">🇧🇫 BF</span>
                      <span class="xp-dash-amount">150,00 USD</span>
                      <span class="xp-dash-method"><img src="/assets/link.svg" alt="Link"></span>
                      <span class="xp-dash-status"><span class="xp-dash-status-badge xp-dash-status-badge--reussi">Réussi</span></span>
                    </div>
                    <div class="xp-dash-row">
                      <span class="xp-dash-client">
                        <span class="xp-dash-avatar xp-dash-avatar-1">IK</span>
                        <span class="xp-dash-client-info">
                          <span class="xp-dash-client-name">Ibrahima Koné</span>
                          <span class="xp-dash-client-date">19 oct. 2026</span>
                        </span>
                      </span>
                      <span class="xp-dash-country">🇳🇬 NG</span>
                      <span class="xp-dash-amount">260,00 USD</span>
                      <span class="xp-dash-method"><img src="/assets/carte_bancaire.svg" alt="Carte bancaire"></span>
                      <span class="xp-dash-status"><span class="xp-dash-status-badge xp-dash-status-badge--reussi">Réussi</span></span>
                    </div>
                    <div class="xp-dash-row">
                      <span class="xp-dash-client">
                        <span class="xp-dash-avatar xp-dash-avatar-2">AS</span>
                        <span class="xp-dash-client-info">
                          <span class="xp-dash-client-name">Aminata Sow</span>
                          <span class="xp-dash-client-date">17 oct. 2026</span>
                        </span>
                      </span>
                      <span class="xp-dash-country">🇫🇷 FR</span>
                      <span class="xp-dash-amount">75,00 USD</span>
                      <span class="xp-dash-method"><img src="/assets/bancontact.svg" alt="Bancontact"></span>
                      <span class="xp-dash-status"><span class="xp-dash-status-badge xp-dash-status-badge--reussi">Réussi</span></span>
                    </div>
                    <div class="xp-dash-row">
                      <span class="xp-dash-client">
                        <span class="xp-dash-avatar xp-dash-avatar-3">OD</span>
                        <span class="xp-dash-client-info">
                          <span class="xp-dash-client-name">Omar Diallo</span>
                          <span class="xp-dash-client-date">15 oct. 2026</span>
                        </span>
                      </span>
                      <span class="xp-dash-country">🇩🇪 DE</span>
                      <span class="xp-dash-amount">540,00 USD</span>
                      <span class="xp-dash-method"><img src="/assets/ideal.svg" alt="iDEAL"></span>
                      <span class="xp-dash-status"><span class="xp-dash-status-badge xp-dash-status-badge--conteste">Contesté</span></span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Connecteur en pointillés (agrafe : bas -> fond -> haut -> gauche) reliant le reçu à la ligne client qui vient d'apparaître (payments.js recalcule "d" à chaque cycle) ; le chevron est un <path> séparé, dessiné à la main (pas un marker SVG) pour rester fiable -->
              <svg class="xp-payments-link" aria-hidden="true">
                <path class="xp-payments-link-path" data-xp-link-path d=""></path>
                <path class="xp-payments-link-chevron" data-xp-link-chevron d=""></path>
              </svg>

              <!-- Pastille montant + moyen de paiement qui glisse le long des pointillés pour donner l'impression d'être déposée sur la ligne du tableau (payments.js anime sa position via getPointAtLength) -->
              <div class="xp-payments-flyer" aria-hidden="true" data-xp-flyer>
                <img data-xp-flyer-icon src="" alt="">
                <span data-xp-flyer-amount></span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Bloc vertical 1 : suivi des transactions en temps réel (même mécanique d'animation que le bloc "Recevez les paiements") -->
    <div class="gf-block gf-vertical gf-vertical-txns">
      <h3 class="gf-vertical-title">Suivez vos transactions <mark>en direct</mark>.</h3>
      <p class="gf-vertical-desc">Chaque paiement reçu apparaît aussitôt dans ce tableau, commission et montant net déjà calculés.</p>
      <div class="xp-txns-table" aria-hidden="true" data-xp-txns-table>
        <div class="xp-txns-thead">
          <span>Client</span><span>Moyen de paiement</span><span>Montant brut</span><span>Commission globale</span><span>Montant net</span>
        </div>
        <div class="xp-txns-row">
          <span class="xp-txns-client">Moussa Ndiaye</span>
          <span class="xp-txns-method"><img src="/assets/mastercard.svg" alt="Mastercard"></span>
          <span class="xp-txns-amount">1 240,00 USD</span>
          <span class="xp-txns-fee">74,40 USD</span>
          <span class="xp-txns-net">1 165,60 USD</span>
        </div>
        <div class="xp-txns-row">
          <span class="xp-txns-client">Fatou Camara</span>
          <span class="xp-txns-method"><img src="/assets/cashapp.svg" alt="Cash App"></span>
          <span class="xp-txns-amount">680,00 USD</span>
          <span class="xp-txns-fee">40,80 USD</span>
          <span class="xp-txns-net">639,20 USD</span>
        </div>
        <div class="xp-txns-row">
          <span class="xp-txns-client">David Osei</span>
          <span class="xp-txns-method"><img src="/assets/apple-pay.svg" alt="Apple Pay"></span>
          <span class="xp-txns-amount">320,00 USD</span>
          <span class="xp-txns-fee">19,20 USD</span>
          <span class="xp-txns-net">300,80 USD</span>
        </div>
        <div class="xp-txns-row">
          <span class="xp-txns-client">Aïcha Traoré</span>
          <span class="xp-txns-method"><img src="/assets/google-pay.svg" alt="Google Pay"></span>
          <span class="xp-txns-amount">950,00 USD</span>
          <span class="xp-txns-fee">57,00 USD</span>
          <span class="xp-txns-net">893,00 USD</span>
        </div>
        <div class="xp-txns-row">
          <span class="xp-txns-client">Pierre Girard</span>
          <span class="xp-txns-method"><img src="/assets/visa.svg" alt="Visa"></span>
          <span class="xp-txns-amount">185,00 USD</span>
          <span class="xp-txns-fee">11,10 USD</span>
          <span class="xp-txns-net">173,90 USD</span>
        </div>
      </div>
    </div>

    <!-- Bloc vertical 2 : rapports financiers (vrais PDF générés par make_reports.py, aperçu dans un modal — données fictives, pas de vrai téléchargement) -->
    <div class="gf-block gf-vertical gf-vertical-reports">
      <h3 class="gf-vertical-title">Consultez vos rapports <mark>financiers</mark>.</h3>
      <p class="gf-vertical-desc">Volume encaissé, commissions et performance des paiements, exportés en PDF prêt à partager.</p>
      <div class="xp-reports-tabs" role="tablist" aria-label="Période du rapport">
        <button type="button" class="xp-reports-tab" data-xp-report-tab="hebdo">Hebdo</button>
        <button type="button" class="xp-reports-tab" data-xp-report-tab="mensuel">Mensuel</button>
        <button type="button" class="xp-reports-tab" data-xp-report-tab="trimestriel">Trim.</button>
        <button type="button" class="xp-reports-tab" data-xp-report-tab="semestriel">Semestre</button>
        <button type="button" class="xp-reports-tab" data-xp-report-tab="annuel">Annuel</button>
      </div>
      <button type="button" class="xp-reports-file" data-xp-report-file aria-haspopup="dialog">
        <span class="xp-reports-file-icon">PDF</span>
        <span class="xp-reports-file-info">
          <span class="xp-reports-file-name" data-xp-report-name>Rapport_mensuel_Xepay_Octobre2026.pdf</span>
          <span class="xp-reports-file-meta" data-xp-report-meta>Octobre 2026 · 6 Ko</span>
        </span>
        <span class="xp-reports-file-view" aria-hidden="true">↗</span>
      </button>
    </div>
  </div>
</section>

<!-- Modal d'aperçu des rapports (données fictives : on affiche, on ne télécharge pas) -->
<div class="xp-report-modal" data-xp-report-modal hidden>
  <div class="xp-report-modal-backdrop" data-xp-report-modal-close></div>
  <div class="xp-report-modal-panel" role="dialog" aria-modal="true" aria-label="Aperçu du rapport">
    <div class="xp-report-modal-bar">
      <span class="xp-report-modal-title" data-xp-report-modal-title>Rapport</span>
      <button type="button" class="xp-report-modal-close" data-xp-report-modal-close aria-label="Fermer l'aperçu">✕</button>
    </div>
    <iframe class="xp-report-modal-frame" data-xp-report-modal-frame title="Aperçu PDF du rapport"></iframe>
  </div>
</div>

<!-- ─── ARCHITECTURE : schéma en 4 niveaux (Stripe / types de traitement / Xepay / Marchand) ─── -->
<section class="arch-section reveal">
  <div class="arch-intro">
    <div class="section-tag">Architecture</div>
    <h2>Derrière chaque paiement, une confiance qui se construit. Xepay relie vos clients, votre entreprise et la puissance de Stripe en une seule expérience fluide — pour que chaque vente en Afrique de l'Ouest s'ouvre, sans friction, sur le monde entier.</h2>
  </div>

  <div class="xp-arch-layers">
    <!-- Niveau 1 : Stripe, avec ses 2 bras horizontaux en pointillés qui
         débutent au milieu (mi-hauteur) du cadre Stripe, à gauche et à
         droite, puis descendent vers les 2 segments extrêmes du switch.
         Le segment central ("Abonnements") reçoit une simple verticale,
         déjà aligné sous Stripe. -->
    <div class="xp-arch-connector">
      <div class="xp-arch-level" style="transition-delay:0.1s">
        <div class="xp-arch-box xp-arch-box--stripe">Stripe</div>
      </div>
      <div class="xp-arch-connector-spacer" aria-hidden="true"></div>
      <span class="xp-arch-bus-arm xp-arch-bus-arm--left" aria-hidden="true" style="transition-delay:0.15s"></span>
      <span class="xp-arch-bus-arm xp-arch-bus-arm--right" aria-hidden="true" style="transition-delay:0.15s"></span>
      <span class="xp-arch-bus-drop xp-arch-bus-drop--left" aria-hidden="true" style="transition-delay:0.2s"></span>
      <span class="xp-arch-bus-drop xp-arch-bus-drop--mid" aria-hidden="true" style="transition-delay:0.25s"></span>
      <span class="xp-arch-bus-drop xp-arch-bus-drop--right" aria-hidden="true" style="transition-delay:0.2s"></span>
    </div>

    <!-- Niveau 2 : types de traitement, switch plat et étiré -->
    <div class="xp-arch-level" style="transition-delay:0.35s">
      <div class="xp-arch-switch">
        <div class="xp-arch-switch-item xp-arch-switch-item--framed is-active">Liens de paiement</div>
        <div class="xp-arch-switch-item">Abonnements</div>
        <div class="xp-arch-switch-item xp-arch-switch-item--framed">Factures</div>
      </div>
    </div>

    <div class="xp-arch-vline xp-arch-vline--single" aria-hidden="true" style="transition-delay:0.45s"></div>

    <!-- Niveau 3 : cadre moyens de paiement tout à gauche, Xepay au centre, commission globale tout à droite.
         Paliers réels de backend/services/commission_service.py (COMMISSION_TIERS), pas des chiffres inventés. -->
    <div class="xp-arch-level" style="transition-delay:0.5s">
      <div class="xp-arch-row">
        <div class="xp-arch-row-side xp-arch-row-side--left">
          <div class="xp-arch-frame">
            <img src="/assets/mastercard.svg" alt="Mastercard">
            <img src="/assets/visa.svg" alt="Visa">
            <img src="/assets/apple-pay.svg" alt="Apple Pay">
            <img src="/assets/google-pay.svg" alt="Google Pay">
            <img src="/assets/cashapp.svg" alt="Cash App">
            <img src="/assets/klarna-logo.svg" alt="Klarna">
          </div>
          <span class="xp-arch-hline" aria-hidden="true"></span>
          <div class="xp-arch-label-box">Moyens de paiement</div>
          <span class="xp-arch-hline" aria-hidden="true"></span>
        </div>
        <div class="xp-arch-box xp-arch-box--xepay">Xepay</div>
        <div class="xp-arch-row-side xp-arch-row-side--right">
          <span class="xp-arch-hline" aria-hidden="true"></span>
          <div class="xp-arch-label-box">Commission globale</div>
          <span class="xp-arch-hline" aria-hidden="true"></span>
          <div class="xp-arch-commission">
            <div class="xp-arch-commission-track" data-xp-commission-track>
              <div class="xp-arch-commission-row"><span>À partir de <strong>0 $</strong></span><strong>6 %</strong></div>
              <div class="xp-arch-commission-row"><span>À partir de <strong>5 000 $</strong></span><strong>5 %</strong></div>
              <div class="xp-arch-commission-row"><span>À partir de <strong>20 000 $</strong></span><strong>4 %</strong></div>
              <div class="xp-arch-commission-row"><span>À partir de <strong>75 000 $</strong></span><strong>3 %</strong></div>
              <div class="xp-arch-commission-row" aria-hidden="true"><span>À partir de <strong>0 $</strong></span><strong>6 %</strong></div>
              <div class="xp-arch-commission-row" aria-hidden="true"><span>À partir de <strong>5 000 $</strong></span><strong>5 %</strong></div>
              <div class="xp-arch-commission-row" aria-hidden="true"><span>À partir de <strong>20 000 $</strong></span><strong>4 %</strong></div>
              <div class="xp-arch-commission-row" aria-hidden="true"><span>À partir de <strong>75 000 $</strong></span><strong>3 %</strong></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="xp-arch-vline xp-arch-vline--single" aria-hidden="true" style="transition-delay:0.65s"></div>

    <!-- Niveau 4 : marchand relié à ses activités par des pointillés en éventail -->
    <div class="xp-arch-level" style="transition-delay:0.7s">
      <div class="xp-arch-box xp-arch-box--marchand">Marchand</div>
      <div class="xp-arch-vline xp-arch-vline--single xp-arch-vline--short" aria-hidden="true"></div>
      <div class="xp-arch-tags-wrap">
        <div class="xp-arch-tags-bus" aria-hidden="true"></div>
        <div class="xp-arch-tags">
          <div class="xp-arch-tag-col"><span class="xp-arch-tag-drop" aria-hidden="true"></span><span class="xp-arch-tag">Clients</span></div>
          <div class="xp-arch-tag-col"><span class="xp-arch-tag-drop" aria-hidden="true"></span><span class="xp-arch-tag">Produits</span></div>
          <div class="xp-arch-tag-col"><span class="xp-arch-tag-drop" aria-hidden="true"></span><span class="xp-arch-tag">Paiements</span></div>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- ─── FEATURE 3 : SOLDE & RETRAITS ─── -->
<section class="feature-section reveal">
  <div class="feature-text">
    <div class="section-tag">Solde</div>
    <h2>Pilotez votre solde <mark>en temps réel</mark>.</h2>
    <p>
      Visualisez vos fonds disponibles et verrouillés, détaillés par
      source de paiement, et retirez-les vers votre compte bancaire
      quand vous le décidez.
    </p>
    <ul class="feature-checklist">
      <li>Détail par source : liens, abonnements, factures</li>
      <li>Montant verrouillé vs disponible, en un coup d'œil</li>
      <li>Retrait à la demande vers votre compte Europe ou US</li>
      <li>Historique complet de chaque retrait</li>
    </ul>
    <a href="/signup" class="btn-primary" style="display:inline-flex">Voir mon solde →</a>
  </div>
  <div class="feature-mockup">
    <div class="feature-mockup-inner">
      <div class="fmock-header">
        <div class="fmock-title">SOLDE</div>
        <div class="fmock-status">USD</div>
      </div>
      <div class="fmock-body">
        <div class="bal-sources">
          <div class="bal-source-row active"><span>Solde principal</span><strong>1 847,30 $US</strong></div>
          <div class="bal-source-row"><span>Paiements par liens</span><strong>1 240,00 $US</strong></div>
          <div class="bal-source-row"><span>Abonnements</span><strong>512,50 $US</strong></div>
          <div class="bal-source-row"><span>Factures</span><strong>94,80 $US</strong></div>
        </div>
        <div class="bal-main">
          <div class="bal-amount">1 847,30 $US</div>
          <div class="bal-bar"><div class="bal-bar-available" style="width:78%"></div><div class="bal-bar-locked" style="width:22%"></div></div>
          <div class="bal-row"><span><span class="bal-dot bal-dot-locked"></span>Montant verrouillé</span><strong>406,40 $US</strong></div>
          <div class="bal-row"><span><span class="bal-dot bal-dot-available"></span>Montant disponible</span><strong>1 440,90 $US</strong></div>
          <button class="bal-withdraw-btn">Retirer des fonds</button>
        </div>
      </div>
    </div>
  </div>
</section>

<div class="section-glow"></div>

<!-- ─── GRILLE FONCTIONNALITÉS ─── -->
<section class="highlights-section reveal">
  <div class="highlights-label">
    <div class="section-tag">Plateforme</div>
    <h3>Tout ce dont vous avez besoin.</h3>
  </div>
  <div class="highlights-grid">
    <div class="highlight-card">
      <div class="hl-image hl-image--frame">
        <div class="hl-frame">
          <div class="hl-frame-bar">
            <span class="hl-frame-dot hl-frame-dot--red"></span>
            <span class="hl-frame-dot hl-frame-dot--yellow"></span>
            <span class="hl-frame-dot hl-frame-dot--green"></span>
          </div>
          <div class="hl-frame-body" data-xp-checkout-demo>
            <img class="hl-frame-step is-active" src="/assets/stripe-checkout-screenshot.png" alt="Page de paiement Stripe">
            <img class="hl-frame-step" src="/assets/stripe-checkout-step2.png" alt="">
            <img class="hl-frame-step" src="/assets/stripe-checkout-step3.png" alt="">
            <img class="hl-frame-step" src="/assets/stripe-checkout-step4.png" alt="">
            <img class="hl-frame-step" src="/assets/stripe-checkout-step5.png" alt="">
            <span class="hl-frame-cursor" data-xp-checkout-cursor aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none"><path d="M4 2 L4 20 L9 15.5 L12.5 22 L15 20.7 L11.3 14 L18 14 Z" fill="#171310" stroke="#ffffff" stroke-width="1.2" stroke-linejoin="round"/></svg>
            </span>
            <span class="hl-frame-type hl-frame-type--number" data-xp-checkout-type="number" aria-hidden="true"></span>
            <span class="hl-frame-type hl-frame-type--expiry" data-xp-checkout-type="expiry" aria-hidden="true"></span>
            <span class="hl-frame-type hl-frame-type--cvc" data-xp-checkout-type="cvc" aria-hidden="true"></span>
          </div>
        </div>
      </div>
      <div class="hl-title">Paiements confirmés instantanément</div>
      <div class="hl-desc">Le paiement de votre client est validé en quelques secondes. Retirez vos fonds à la demande vers votre compte bancaire.</div>
    </div>
    <div class="highlight-card">
      <div class="hl-image hl-image--dash">
        <div class="hl-dash">
          <div class="hl-dash-top">
            <span class="hl-dash-title">Équipe</span>
            <button type="button" class="hl-dash-invite-btn" data-xp-team-invite>+ Inviter</button>
          </div>
          <div class="hl-dash-invite-row">
            <span class="hl-dash-invite-field">email@exemple.com</span>
            <span class="hl-dash-invite-role">Manager</span>
          </div>
          <div class="hl-dash-table" data-xp-team-table>
            <div class="hl-dash-row hl-dash-row--head"><span>Membre</span><span>Rôle</span></div>
            <div class="hl-dash-row"><span class="hl-dash-member"><span class="hl-dash-avatar">A</span>Aminata D.</span><span class="hl-dash-badge hl-dash-badge--admin">Admin</span></div>
            <div class="hl-dash-row"><span class="hl-dash-member"><span class="hl-dash-avatar">K</span>Kwame A.</span><span class="hl-dash-badge hl-dash-badge--manager">Manager</span></div>
            <div class="hl-dash-row"><span class="hl-dash-member"><span class="hl-dash-avatar">S</span>Sophie L.</span><span class="hl-dash-badge hl-dash-badge--read">Lecture</span></div>
          </div>
        </div>
      </div>
      <div class="hl-title">Équipe & rôles</div>
      <div class="hl-desc">Invitez votre équipe avec des rôles définis (admin, manager, lecture) — accès tracés et sécurisés.</div>
    </div>
    <div class="highlight-card">
      <div class="hl-image"><img src="/assets/illu-account-security.svg" alt=""></div>
      <div class="hl-title">Sécurité du compte</div>
      <div class="hl-desc">Double authentification, clés d'accès (passkeys) et connexion Google pour protéger votre compte.</div>
    </div>
    <div class="highlight-card">
      <div class="hl-image"><img src="/assets/illu-payment-security.svg" alt=""></div>
      <div class="hl-title">Sécurité des paiements</div>
      <div class="hl-desc">Paiements traités par Stripe, certifié PCI DSS niveau 1. 3D Secure et détection de fraude Stripe Radar.</div>
    </div>
    <div class="highlight-card">
      <div class="hl-image"><img src="/assets/illu-webhooks.svg" alt=""></div>
      <div class="hl-title">Webhooks</div>
      <div class="hl-desc">Recevez vos événements de paiement en temps réel pour vos propres intégrations.</div>
    </div>
    <div class="highlight-card">
      <div class="hl-image"><video src="/assets/illu-company-formation-preview.mp4" autoplay muted loop playsinline></video></div>
      <div class="hl-title">Pas encore de société US ?</div>
      <div class="hl-desc">Formez votre LLC via Firstbase ou Stripe Atlas, directement depuis vos paramètres Xepay.</div>
    </div>
  </div>
</section>

<!-- ─── CTA ─── -->
<section class="cta-section">
  <div class="cta-inner reveal">
    <h2>Prêt à <mark>encaisser le monde</mark> ?</h2>
    <p>Rejoignez les marchands qui font confiance à Xepay pour encaisser leurs paiements à travers l'UEMOA. Inscription gratuite, sans engagement.</p>
    <div class="cta-actions">
      <a href="/signup" class="btn-primary" style="font-size:15px;padding:17px 34px">Créer mon compte — Gratuit</a>
      <a href="mailto:support@alasdia.com" class="btn-ghost" style="font-size:14px;padding:16px 28px">Contacter l'équipe</a>
    </div>
  </div>
</section>
</div>
`;
}

export function mount(root) {
  const cleanupGlobe = mountGlobe(root);
  const cleanupGlobeBg = mountGlobeBg(root);
  const cleanupArchitecture = mountArchitecture(root);
  const cleanupPayments = mountPayments(root);
  const cleanupTransactions = mountTransactions(root);
  const cleanupReports = mountReports(root);
  const cleanupTeam = mountTeam(root);
  const cleanupCheckoutDemo = mountCheckoutDemo(root);
  return function cleanupAll() {
    cleanupGlobe();
    cleanupGlobeBg();
    cleanupArchitecture();
    cleanupPayments();
    cleanupTransactions();
    cleanupReports();
    cleanupTeam();
    cleanupCheckoutDemo();
  };
}
