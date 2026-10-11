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
//     exactement de la largeur du tiroir ouvert (margin-right dynamique via
//     --xepay-drawer-width) ; sidebar jamais touchée ; aucun voile/overlay
//     grisé — le contenu rétréci reste pleinement interactif.
//   - Écran moyen : superposition classique (le tiroir recouvre le
//     contenu, voile assombri conservé), sans rétrécir #main-content.
//   - Mobile (<=640px) : le tiroir occupe toute la largeur de l'écran.

const LARGE_SCREEN_QUERY = "(min-width: 1200px)";
const STYLE_ID = "xepay-details-drawer-style";
const DEFAULT_WIDTH = 480;

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
            width: min(var(--xepay-drawer-width, ${DEFAULT_WIDTH}px), 100%);
            max-width: 100%;
            height: 100%;
            max-height: 100%;
            margin: 0;
            border-radius: 0;
            box-shadow: -12px 0 40px rgba(0, 0, 0, .18);
            display: flex;
            flex-direction: column;
            overflow-y: auto;
            pointer-events: auto;
        }
        .customer-modal-overlay.xepay-drawer.open .xepay-drawer-panel {
            animation: xepayDrawerSlideIn .25s ease;
        }

        /* ================================================
           Bootstrap (.modal) — Rapport de solde Stripe
           !important nécessaire : .modal-lg/.modal-dialog-centered/
           .modal-dialog-scrollable (déjà posées sur ce modal) ont plus de
           sélecteurs de classe que les miens et gagneraient sinon la
           bataille de spécificité CSS sur width/max-width/position.
        ================================================ */
        .modal.xepay-drawer .modal-dialog {
            position: fixed !important;
            top: 0 !important;
            right: 0 !important;
            bottom: 0 !important;
            left: auto !important;
            margin: 0 !important;
            max-width: min(var(--xepay-drawer-width, ${DEFAULT_WIDTH}px), 100vw) !important;
            width: 100% !important;
            height: 100% !important;
            display: flex !important;
        }
        .modal.xepay-drawer .xepay-drawer-panel {
            width: 100%;
            height: 100%;
            max-height: 100%;
            border-radius: 0;
            border: none;
            box-shadow: -12px 0 40px rgba(0, 0, 0, .18);
            overflow-y: auto;
            pointer-events: auto;
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
                width: 100% !important;
                max-width: 100% !important;
            }
        }

        /* ================================================
           GRAND ÉCRAN (push) : le contenu principal se rétrécit exactement
           de la largeur du tiroir ouvert, la sidebar n'est JAMAIS touchée,
           et le fond assombri (overlay maison + .modal-backdrop Bootstrap)
           est neutralisé — sans ça, le voile semi-transparent couvrant tout
           le viewport (inset:0) donnait l'impression que la sidebar et le
           contenu étaient "recouverts" même une fois le panneau rétréci à
           droite. Sur écran moyen/mobile (hors de cette media query) :
           superposition classique inchangée (voile assombri conservé).
        ================================================ */
        @media (min-width: 1200px) {
            /* flex:1 1 auto + width:auto annulent la largeur explicite
               propre à chaque vue (calc(100% - 18%) sur sidebar.css,
               flex-grow:1 + margin-left fixe sur transactions.css, etc.)
               pour laisser margin-right réserver proprement la place du
               tiroir, quelle que soit la formule d'origine de la vue
               affichée. La sidebar (hors de ce sélecteur) garde sa largeur
               et sa position intactes. --xepay-drawer-width est posée par
               initDetailsDrawer() ci-dessous, propre à chaque tiroir. */
            body.xepay-drawer-open #main-content {
                flex: 1 1 auto !important;
                width: auto !important;
                margin-right: var(--xepay-drawer-width, ${DEFAULT_WIDTH}px) !important;
                transition: margin-right .25s ease;
            }

            /* Overlay maison : fond transparent + clic traversant (le
               panneau garde pointer-events:auto ci-dessus), pour que le
               contenu rétréci reste pleinement interactif. */
            body.xepay-drawer-open .customer-modal-overlay.xepay-drawer {
                background: transparent !important;
                backdrop-filter: none !important;
                pointer-events: none !important;
            }

            /* Backdrop Bootstrap : posé par le JS de Bootstrap comme frère
               dans <body>, jamais grisé en mode "push". */
            body.xepay-drawer-open .modal-backdrop {
                opacity: 0 !important;
                pointer-events: none !important;
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
 * @param {{ width?: number }} [options] - largeur du tiroir en px
 *   (défaut 480) ; le "push" de #main-content réserve exactement cette
 *   largeur, quelle que soit la valeur choisie par l'appelant.
 */
export function initDetailsDrawer(overlayEl, panelEl, { width = DEFAULT_WIDTH } = {}) {
    if (!overlayEl || !panelEl) return;

    ensureDrawerStyles();

    overlayEl.classList.add("xepay-drawer");
    panelEl.classList.add("xepay-drawer-panel");
    panelEl.style.setProperty("--xepay-drawer-width", `${width}px`);

    const largeScreen = window.matchMedia(LARGE_SCREEN_QUERY);

    function isOpen() {
        return (
            overlayEl.classList.contains("open") ||
            overlayEl.classList.contains("show")
        );
    }

    function syncPush() {
        const push = isOpen() && largeScreen.matches;
        if (push) {
            // Posée sur <body> (lu par la media query ci-dessus pour
            // #main-content) uniquement pendant que CE tiroir est ouvert —
            // un seul tiroir de détails est ouvert à la fois dans l'app.
            document.body.style.setProperty("--xepay-drawer-width", `${width}px`);
        }
        document.body.classList.toggle("xepay-drawer-open", push);
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
