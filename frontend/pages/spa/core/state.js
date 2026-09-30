// État global utilisateur/workspace — source unique de vérité pour le JWT,
// le workspace actif et le plan en cache. Rétrocompatible avec les clés
// localStorage déjà utilisées par l'app (token, workspace_id, email, plan)
// pour ne rien casser côté persistance navigateur existante.

const LS_TOKEN = "token";
const LS_WORKSPACE = "workspace_id";
const LS_EMAIL = "email";
const LS_PLAN = "plan";

export function getToken() {
  return localStorage.getItem(LS_TOKEN);
}

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

export function setSession({ token, workspaceId, email } = {}) {
  if (token) localStorage.setItem(LS_TOKEN, token);
  if (workspaceId) localStorage.setItem(LS_WORKSPACE, workspaceId);
  if (email) localStorage.setItem(LS_EMAIL, email);
}

export function setWorkspaceId(workspaceId) {
  if (workspaceId) localStorage.setItem(LS_WORKSPACE, workspaceId);
}

export function clearSession() {
  localStorage.removeItem(LS_TOKEN);
  localStorage.removeItem(LS_WORKSPACE);
  localStorage.removeItem(LS_EMAIL);
  localStorage.removeItem(LS_PLAN);
}

export function isAuthenticated() {
  return !!getToken();
}
