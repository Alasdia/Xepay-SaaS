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

// Retourne une promesse résolue une fois les CSS demandés chargés (ou en
// échec — ne bloque jamais indéfiniment) : permet au router d'attendre que
// le style de la vue soit prêt avant d'injecter son HTML, pour ne jamais
// afficher de contenu non stylé.
export function setViewStyles(hrefs = []) {
  currentLinks.forEach((link) => link.remove());
  const loaded = [];
  currentLinks = hrefs.map((href) => {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = toRootRelative(href);
    link.dataset.viewStyle = "true";
    loaded.push(
      new Promise((resolve) => {
        link.addEventListener("load", resolve, { once: true });
        link.addEventListener("error", resolve, { once: true });
      })
    );
    document.head.appendChild(link);
    return link;
  });
  const timeout = new Promise((resolve) => setTimeout(resolve, 4000));
  return Promise.race([Promise.all(loaded), timeout]);
}
