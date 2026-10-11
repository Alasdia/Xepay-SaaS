// Tiroir latéral droit partagé pour les modals de CONSULTATION DE DÉTAILS
// (uniquement) : Clients, Produits (commerce.js) et Rapport de solde
// Stripe (transactions.js). Explicitement exclu : création, modification,
// résiliation, upgrade — ces modals gardent leur présentation centrée
// actuelle, inchangée.
//
// Ne touche ni au contenu, ni aux actions/boutons, ni à la logique
// d'ouverture/fermeture existante de chaque modal (classList "open" pour
// le système maison .customer-modal-overlay, API Bootstrap pour
// #stripeReportModal) : ce module se contente d'ajouter des classes CSS et
// d'observer les deux mécanismes pour synchroniser le "push" du contenu
// principal sur grand écran.
//
// Comportement responsive :
//   - Grand écran (>=1200px) : contenu principal (#main-content) rétréci
//     (margin-right), le tiroir ne le recouvre pas.
//   - Écran moyen : superposition classique (le tiroir recouvre le
//     contenu, comme un modal), sans rétrécir #main-content.
//   - Mobile (<=640px) : le tiroir occupe toute la largeur de l'écran.

const LARGE_SCREEN_QUERY = "(min-width: 1200px)";
const STYLE_ID = "xepay-details-drawer-style";

function ensureDrawerStyles() {
    if (document.querySelector(`#${STYLE_ID}`)) return;

    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
        /* ================================================
           Système maison (.customer-modal-overlay) —
           Clients / Produits
        ================================================ */
        .customer-modal-overlay.xepay-drawer {
            align-items: stretch !important;
            justify-content: flex-end !important;
            padding: 0 !important;
        }
        .customer-modal-overlay.xepay-drawer .xepay-drawer-panel {
            width: min(480px, 100%);
            max-width: 100%;
            height: 100%;
            max-height: 100%;
            margin: 0;
            border-radius: 0;
            box-shadow: -12px 0 40px rgba(0, 0, 0, .18);
            display: flex;
            flex-direction: column;
            overflow-y: auto;
        }
        .customer-modal-overlay.xepay-drawer.open .xepay-drawer-panel {
            animation: xepayDrawerSlideIn .25s ease;
        }

        /* ================================================
           Bootstrap (.modal) — Rapport de solde Stripe
        ================================================ */
        .modal.xepay-drawer .modal-dialog {
            position: fixed !important;
            top: 0;
            right: 0;
            bottom: 0;
            left: auto !important;
            margin: 0 !important;
            max-width: min(560px, 100%);
            width: 100%;
            height: 100%;
            display: flex;
        }
        .modal.xepay-drawer .xepay-drawer-panel {
            width: 100%;
            height: 100%;
            max-height: 100%;
            border-radius: 0;
            border: none;
            box-shadow: -12px 0 40px rgba(0, 0, 0, .18);
            overflow-y: auto;
        }
        .modal.xepay-drawer.show .xepay-drawer-panel {
            animation: xepayDrawerSlideIn .25s ease;
        }

        @keyframes xepayDrawerSlideIn {
            from { transform: translateX(100%); }
            to { transform: translateX(0); }
        }

        /* Mobile : plein écran */
        @media (max-width: 640px) {
            .customer-modal-overlay.xepay-drawer .xepay-drawer-panel,
            .modal.xepay-drawer .modal-dialog {
                width: 100%;
                max-width: 100%;
            }
        }

        /* Grand écran : le tiroir rétrécit le contenu principal au lieu de
           le recouvrir — sur écran moyen, superposition classique
           (inchangée). Rétrécit l'espace disponible au niveau de <body>
           plutôt que de surcharger la largeur de #main-content : chaque
           vue définit #main-content différemment (calc(100% - 18%) sur
           sidebar.css, flex-grow:1 + margin-left fixe sur transactions.css,
           etc.) — recalculer "100%" une fois ici, au niveau du body, reste
           correct quelle que soit la formule propre à la vue affichée. */
        @media (min-width: 1200px) {
            body.xepay-drawer-open {
                box-sizing: border-box;
                padding-right: 480px;
                transition: padding-right .25s ease;
            }
        }
    `;
    document.head.appendChild(style);
}

/**
 * Transforme un modal de détails existant (overlay + panneau intérieur) en
 * tiroir latéral droit, sans changer sa logique d'ouverture/fermeture.
 * @param {HTMLElement} overlayEl - l'élément overlay/modal lui-même
 *   (.customer-modal-overlay ou .modal Bootstrap).
 * @param {HTMLElement} panelEl - le panneau visuel à l'intérieur
 *   (.customer-modal ou .modal-content).
 */
export function initDetailsDrawer(overlayEl, panelEl) {
    if (!overlayEl || !panelEl) return;

    ensureDrawerStyles();

    overlayEl.classList.add("xepay-drawer");
    panelEl.classList.add("xepay-drawer-panel");

    const largeScreen = window.matchMedia(LARGE_SCREEN_QUERY);

    function isOpen() {
        return (
            overlayEl.classList.contains("open") ||
            overlayEl.classList.contains("show")
        );
    }

    function syncPush() {
        document.body.classList.toggle(
            "xepay-drawer-open",
            isOpen() && largeScreen.matches
        );
    }

    // Système maison : ouverture/fermeture via classList("open") — observé
    // plutôt qu'intercepté, pour ne jamais changer le comportement
    // existant des boutons qui l'ajoutent/le retirent.
    const observer = new MutationObserver(syncPush);
    observer.observe(overlayEl, { attributes: true, attributeFilter: ["class"] });

    // Bootstrap : événements natifs de show/hide du modal.
    overlayEl.addEventListener("shown.bs.modal", syncPush);
    overlayEl.addEventListener("hidden.bs.modal", syncPush);

    largeScreen.addEventListener("change", syncPush);
}
