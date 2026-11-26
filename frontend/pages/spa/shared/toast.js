// Toast partagé — consolidation de la copie identique trouvée dans
// dashboard.js, profil.js, sécurité.js et transactions.js (4 des 7 copies
// dupliquées relevées dans l'audit). API.js utilise un toast structurellement
// différent (#toast/#toastMsg, sans conteneur empilable) conservé tel quel
// dans sa propre vue pour ne pas altérer son rendu visuel. liens.js
// utilise alert() natif et n'a pas de #toast-container dans son markup :
// non touché, pour ne pas introduire de changement UI/UX.

export function showToast(message, type = "success") {
  const container = document.getElementById("toast-container");
  if (!container) return;
  // Largeur/position calées sur le rect réel de #main-content (demande du
  // 2026-11-26 : toast à 90% de la largeur de la vue/sous-vue active) -
  // jamais une valeur CSS fixe (left/width en %), car plusieurs vues
  // surchargent elles-mêmes #main-content avec des unités différentes
  // (px vs %, voir dashboard.css vs sidebar.css) selon le CSS actif à cet
  // instant (styleLoader.js). Même principe que showSkeleton (router.js).
  const mainContent = document.getElementById("main-content");
  if (mainContent) {
    const rect = mainContent.getBoundingClientRect();
    container.style.left = `${rect.left}px`;
    container.style.width = `${rect.width}px`;
  }
  const toast = document.createElement("div");
  toast.className = `toast-notif-item ${type}`;
  toast.innerHTML = `<span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.animation = "toastOut 0.3s ease forwards";
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}
