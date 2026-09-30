// Client API centralisant l'URL de base et les headers Authorization +
// X-Workspace-Id, en remplacement des ~66 constructions manuelles
// dispersées dans les anciens fichiers de page. Le comportement des
// réponses (res.ok, res.status, res.json()) reste identique à l'existant :
// ce module ne fait que construire la requête, chaque vue garde sa propre
// gestion des erreurs telle quelle.

import { getToken, getWorkspaceId } from "./state.js";

const BASE_URL = "https://api.alasdia.com";

export function apiFetch(path, options = {}) {
  const { method = "GET", headers = {}, body, ...rest } = options;
  const finalHeaders = { ...headers };

  const token = getToken();
  if (token) finalHeaders["Authorization"] = "Bearer " + token;

  const workspaceId = getWorkspaceId();
  if (workspaceId) finalHeaders["X-Workspace-Id"] = workspaceId;

  let finalBody = body;
  const isPlainBody = body !== undefined && !(body instanceof FormData) && typeof body !== "string";
  if (isPlainBody) {
    finalHeaders["Content-Type"] = "application/json";
    finalBody = JSON.stringify(body);
  }

  return fetch(BASE_URL + path, { method, headers: finalHeaders, body: finalBody, ...rest });
}

export const apiClient = {
  fetch: apiFetch,
  get: (path, options) => apiFetch(path, { ...options, method: "GET" }),
  post: (path, body, options) => apiFetch(path, { ...options, method: "POST", body }),
  put: (path, body, options) => apiFetch(path, { ...options, method: "PUT", body }),
  delete: (path, options) => apiFetch(path, { ...options, method: "DELETE" }),
};
