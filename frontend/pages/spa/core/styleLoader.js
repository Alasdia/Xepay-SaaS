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

// Retourne une promesse résolue une fois les CSS demandés chargés, ou
// REJETÉE si l'un d'eux a échoué (ex. hors ligne) - CORRIGÉ le
// 2026-11-26 : l'ancienne version résolvait aussi sur l'événement
// "error" du <link>, exactement comme un succès - le router continuait
// donc à afficher la vue (son HTML réel) sans jamais avoir réellement
// chargé son CSS, d'où du HTML brut non stylé plutôt qu'un message
// clair. Un simple ralentissement (timeout 4s sans ni load ni error)
// reste traité comme un succès - seul un VRAI échec réseau (error) fait
// désormais rejeter, voir router.js pour l'écran de secours qui
// intercepte ce rejet.
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
        link.addEventListener("load", () => resolve(true), { once: true });
        link.addEventListener("error", () => resolve(false), { once: true });
      })
    );
    document.head.appendChild(link);
    return link;
  });
  const timeout = new Promise((resolve) => setTimeout(() => resolve("timeout"), 4000));
  return Promise.race([Promise.all(loaded), timeout]).then((result) => {
    if (result === "timeout") return;
    if (result.some((ok) => ok === false)) {
      throw new Error("Impossible de charger le style de cette vue (hors ligne ?).");
    }
  });
}
