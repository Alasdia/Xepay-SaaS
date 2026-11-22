// Petit modal de chargement affiché pendant un changement de workspace
// (même principe que le "Changement de compte" de Stripe) - markup statique
// dans dashboard.html (#workspace-switch-overlay, toujours présent, comme
// #toast-container), affiché/masqué ici plutôt que créé/détruit à chaque
// fois. Voile de fond (backdrop) qui bloque toute interaction, mais la
// boîte elle-même reste petite (titre = nom du workspace, cercle de
// chargement, sous-titre) - pas un plein écran opaque.

export function showWorkspaceSwitchOverlay(workspaceName) {
  const el = document.getElementById("workspace-switch-overlay");
  if (!el) return;
  const title = el.querySelector("#workspace-switch-overlay-title");
  if (title) title.textContent = workspaceName || "Workspace";
  el.style.display = "flex";
}

export function hideWorkspaceSwitchOverlay() {
  const el = document.getElementById("workspace-switch-overlay");
  if (el) el.style.display = "none";
}
