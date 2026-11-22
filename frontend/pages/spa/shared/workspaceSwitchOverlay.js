// Overlay plein écran bloquant affiché pendant un changement de workspace
// (même principe que le "Changement de compte" de Stripe) - markup statique
// dans dashboard.html (#workspace-switch-overlay, toujours présent, comme
// #toast-container), affiché/masqué ici plutôt que créé/détruit à chaque
// fois.

export function showWorkspaceSwitchOverlay() {
  const el = document.getElementById("workspace-switch-overlay");
  if (el) el.style.display = "flex";
}

export function hideWorkspaceSwitchOverlay() {
  const el = document.getElementById("workspace-switch-overlay");
  if (el) el.style.display = "none";
}
