// État global utilisateur/workspace — depuis la migration vers des cookies
// de session HttpOnly, le JWT ne vit plus jamais côté JS (illisible, posé
// par le backend). localStorage ne garde que des informations non
// sensibles (workspace actif, email, plan en cache) + un simple indicateur
// local "has_session" : il ne fait QUE refléter qu'un login a réussi à un
// moment donné, ce n'est jamais la source de vérité de l'authentification
// (seul le cookie HttpOnly, vérifié serveur, tranche réellement) — un
// cookie expiré sans indicateur à jour est intercepté par apiClient.js
// (401 -> tentative de /refresh -> redirection vers /login si ça échoue
// aussi). Rétrocompatible avec les clés déjà utilisées (workspace_id,
// email, plan) pour ne rien casser côté persistance navigateur existante.

const LS_SESSION_HINT = "has_session";
const LS_WORKSPACE = "workspace_id";
const LS_EMAIL = "email";
const LS_PLAN = "plan";

export function getWorkspaceId() {
  return localStorage.getItem(LS_WORKSPACE);
}

export function getEmail() {
  return localStorage.getItem(LS_EMAIL);
}

export function getPlan() {
  return localStorage.getItem(LS_PLAN);
}

export function setPlan(plan) {
  if (plan) localStorage.setItem(LS_PLAN, plan);
}

export function setSession({ workspaceId, email } = {}) {
  localStorage.setItem(LS_SESSION_HINT, "1");
  if (workspaceId) localStorage.setItem(LS_WORKSPACE, workspaceId);
  if (email) localStorage.setItem(LS_EMAIL, email);
}

export function setWorkspaceId(workspaceId) {
  if (workspaceId) localStorage.setItem(LS_WORKSPACE, workspaceId);
}

export function clearSession() {
  localStorage.removeItem(LS_SESSION_HINT);
  localStorage.removeItem(LS_WORKSPACE);
  localStorage.removeItem(LS_EMAIL);
  localStorage.removeItem(LS_PLAN);
}

export function isAuthenticated() {
  return localStorage.getItem(LS_SESSION_HINT) === "1";
}
