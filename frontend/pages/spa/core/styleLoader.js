// Charge/décharge dynamiquement le(s) CSS propre(s) à la vue active, pour
// éviter les collisions entre les 14 fichiers CSS existants (jamais conçus
// pour cohabiter dans un même document). Les CSS globaux (bootstrap,
// sidebar.css, modal-upgrade.css, responsive.css, polices) restent chargés
// en permanence dans le <head> du shell.

let currentLinks = [];

// Les vues passent des noms de fichiers relatifs (ex: "dashboard.css") : on
// les normalise ici en chemins root-relative pour qu'ils restent valides
// quel que soit le pathname courant (/dash/workspace/{id}/...), sans avoir
// à toucher chaque point d'appel dans les 7 vues.
function toRootRelative(href) {
  if (/^([a-z]+:)?\/\//i.test(href) || href.startsWith("/")) return href;
  return "/" + href;
}

export function setViewStyles(hrefs = []) {
  currentLinks.forEach((link) => link.remove());
  currentLinks = hrefs.map((href) => {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = toRootRelative(href);
    link.dataset.viewStyle = "true";
    document.head.appendChild(link);
    return link;
  });
}
