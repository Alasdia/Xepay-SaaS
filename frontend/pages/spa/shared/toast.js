// Toast partagé — consolidation de la copie identique trouvée dans
// dashboard.js, profil.js, sécurité.js et transactions.js (4 des 7 copies
// dupliquées relevées dans l'audit). API.js utilise un toast structurellement
// différent (#toast/#toastMsg, sans conteneur empilable) conservé tel quel
// dans sa propre vue pour ne pas altérer son rendu visuel. liens.js et
// multi-users.js utilisent alert() natif et n'ont pas de #toast-container
// dans leur markup : non touchés, pour ne pas introduire de changement UI/UX.

export function showToast(message, type = "success") {
  const container = document.getElementById("toast-container");
  if (!container) return;
  const icons = { success: "✅", error: "⚠️", warning: "⏳" };
  const toast = document.createElement("div");
  toast.className = `toast-notif-item ${type}`;
  toast.innerHTML = `<span class="icon">${icons[type] || icons.success}</span><span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.animation = "toastOut 0.3s ease forwards";
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}
