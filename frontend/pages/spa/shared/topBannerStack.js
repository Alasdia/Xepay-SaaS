// Décalage de #sidebar/#main-content sous #top-banner + N bandeaux
// empilés (ex. llcBanner.js, postLlcOnboardingBanner.js) - extrait le
// 2026-11-27 (ajout du 2e bandeau) pour que CHAQUE bandeau recalcule le
// total à partir de TOUS les bandeaux ".top-stack-banner" actuellement
// visibles, plutôt que chacun ne connaisse que sa propre hauteur :
// aujourd'hui ces 2 bandeaux sont mutuellement exclusifs (l'un exige
// Buildness "completed", l'autre son contraire), mais s'ils ne
// recalculaient QUE leur propre hauteur, le dernier des 2
// addEventListener("resize", ...) à se déclencher écraserait l'offset
// posé par l'autre avec une valeur fausse (0 pour celui qui est
// masqué) - en sommant tout ce qui est visible à chaque appel, peu
// importe lequel des 2 scripts déclenche le recalcul, le résultat est
// toujours correct.
export function applyTopStackOffset() {
  const topBanner = document.getElementById("top-banner");
  const sidebar = document.getElementById("sidebar");
  const mainContent = document.getElementById("main-content");
  if (!topBanner || !sidebar || !mainContent) return;

  let total = topBanner.getBoundingClientRect().height;
  document.querySelectorAll(".top-stack-banner").forEach((el) => {
    if (el.style.display !== "none") total += el.getBoundingClientRect().height;
  });

  sidebar.style.top = `${total}px`;
  sidebar.style.height = `calc(100vh - ${total}px)`;
  mainContent.style.marginTop = `${total}px`;
}

// Un seul listener "resize" partagé entre tous les bandeaux empilés
// (idempotent - un 2e appel depuis un autre bandeau ne ré-attache rien)
// plutôt qu'un par bandeau, qui recalculeraient tous la même chose en
// double à chaque redimensionnement.
let _wired = false;
export function initTopStackResizeListener() {
  if (_wired) return;
  _wired = true;
  window.addEventListener("resize", applyTopStackOffset);
}
