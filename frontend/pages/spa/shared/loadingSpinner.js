// Élément de chargement partagé (demande du 2026-11-25, généralisé depuis
// l'onglet Configuration Shopify) - un cercle tournant (bordure 2px) suivi
// de "Chargement...", à utiliser à la place d'un message texte seul pour
// tout contenu de section/onglet qui prend du temps à charger. Le markup
// est partagé (comme toast.js), mais le CSS (.view-loading/
// .view-loading-spinner) doit être dupliqué dans le CSS propre à chaque
// vue (setViewStyles n'en charge qu'un à la fois par convention - voir
// .toast-notif-item, dupliqué dans 7 fichiers CSS pour la même raison).
export function viewLoadingHtml(message = "Chargement...") {
    return `
        <div class="view-loading">
            <div class="view-loading-spinner"></div>
            <p>${message}</p>
        </div>
    `;
}
