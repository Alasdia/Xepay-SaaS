// Client API centralisant l'URL de base et le header X-Workspace-Id, en
// remplacement des ~66 constructions manuelles dispersées dans les anciens
// fichiers de page. Le comportement des réponses (res.ok, res.status,
// res.json()) reste identique à l'existant : ce module ne fait que
// construire la requête, chaque vue garde sa propre gestion des erreurs
// telle quelle.
//
// Migration cookies de session (voir audit) : plus de JWT en localStorage
// ni de header Authorization — le navigateur attache seul le cookie
// HttpOnly via `credentials: "include"`. Un header X-CSRF-Token (lu depuis
// le cookie non-HttpOnly csrf_token, pattern double-submit) accompagne
// chaque requête mutative. Sur un 401, un seul /refresh partagé est tenté
// (mutex ci-dessous) puis la requête d'origine est rejouée une fois au
// maximum ; si le refresh échoue aussi, la session locale est effacée et
// l'utilisateur est renvoyé vers /login.

import { getWorkspaceId, clearSession } from "./state.js";

const BASE_URL = "https://aws.api.alasdia.com";
const CSRF_COOKIE_NAME = "csrf_token";
const MUTATING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

function getCsrfToken() {
  const match = document.cookie.match(
    new RegExp("(?:^|; )" + CSRF_COOKIE_NAME + "=([^;]*)")
  );
  return match ? decodeURIComponent(match[1]) : null;
}

function buildRequest(path, options) {
  const { method = "GET", headers = {}, body, ...rest } = options;
  const upperMethod = method.toUpperCase();
  const finalHeaders = { ...headers };

  const workspaceId = getWorkspaceId();
  if (workspaceId) finalHeaders["X-Workspace-Id"] = workspaceId;

  if (MUTATING_METHODS.has(upperMethod)) {
    const csrfToken = getCsrfToken();
    if (csrfToken) finalHeaders["X-CSRF-Token"] = csrfToken;
  }

  let finalBody = body;
  const isPlainBody = body !== undefined && !(body instanceof FormData) && typeof body !== "string";
  if (isPlainBody) {
    finalHeaders["Content-Type"] = "application/json";
    finalBody = JSON.stringify(body);
  }

  return fetch(BASE_URL + path, {
    method: upperMethod,
    headers: finalHeaders,
    body: finalBody,
    credentials: "include",
    ...rest,
  });
}

// Mutex de refresh : sous requêtes concurrentes (ex. Promise.all de
// plusieurs apiFetch), toutes partagent la MÊME tentative de /refresh au
// lieu d'en déclencher chacune une — indispensable avec un refresh token
// qui tourne à chaque usage (voir backend/services/refresh_token_service.py
// et l'audit : sans ce verrou, les requêtes perdantes de la course
// invalideraient la session des autres).
let refreshPromise = null;

function refreshSession() {
  if (!refreshPromise) {
    const csrfToken = getCsrfToken();
    refreshPromise = fetch(BASE_URL + "/refresh", {
      method: "POST",
      credentials: "include",
      headers: csrfToken ? { "X-CSRF-Token": csrfToken } : {},
    })
      .then((res) => res.ok)
      .catch(() => false)
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

export async function apiFetch(path, options = {}, _isRetry = false) {
  const response = await buildRequest(path, options);

  // Un seul rejeu maximum par requête d'origine (_isRetry), et /refresh ne
  // se déclenche jamais sur lui-même pour éviter toute boucle.
  if (response.status === 401 && !_isRetry && path !== "/refresh") {
    const refreshed = await refreshSession();
    if (refreshed) {
      return apiFetch(path, options, true);
    }
    clearSession();
    window.location.href = "/login";
  }

  return response;
}

export const apiClient = {
  fetch: apiFetch,
  get: (path, options) => apiFetch(path, { ...options, method: "GET" }),
  post: (path, body, options) => apiFetch(path, { ...options, method: "POST", body }),
  put: (path, body, options) => apiFetch(path, { ...options, method: "PUT", body }),
  delete: (path, options) => apiFetch(path, { ...options, method: "DELETE" }),
};
