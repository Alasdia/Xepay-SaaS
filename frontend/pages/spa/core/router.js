// Router maison — history.pushState/popstate, sans dépendance externe.
// Chaque route associe un pattern de path (params :nommés) à une fonction
// mountView(container, params) qui doit retourner { unmount() } (ou rien).
// Le router se charge d'appeler unmount() de la vue précédente avant de
// monter la suivante, et gère les routes protégées (redirection login).

// Loader commun aux 7 vues, affiché immédiatement dans #main-content dès
// qu'une navigation démarre (la sidebar n'est jamais touchée) et remplacé
// par le HTML réel de la vue seulement une fois son CSS chargé (voir
// core/styleLoader.js) — le contenu non stylé n'est ainsi jamais visible.
const LOADER_HTML = `
<div class="spa-route-loader" style="display:flex;align-items:center;justify-content:center;min-height:60vh;">
  <div class="spinner-border" role="status" style="width:3rem;height:3rem;color:#facc15;">
    <span class="visually-hidden">Chargement...</span>
  </div>
</div>
`;

const routes = [];
let currentUnmount = null;
let isAuthenticated = () => true;
let onUnauthorized = () => {
  window.location.href = "/login.html";
};
let onRouteChange = () => {};

export function configure({ isAuthenticated: authFn, onUnauthorized: unauthFn, onRouteChange: changeFn } = {}) {
  if (authFn) isAuthenticated = authFn;
  if (unauthFn) onUnauthorized = unauthFn;
  if (changeFn) onRouteChange = changeFn;
}

export function registerRoute(pattern, mountView, { protected: isProtected = true, name } = {}) {
  const paramNames = [];
  const regex = new RegExp(
    "^" +
      pattern
        .split("/")
        .map((segment) => {
          if (segment.startsWith(":")) {
            paramNames.push(segment.slice(1));
            return "([^/]+)";
          }
          return segment;
        })
        .join("/") +
      "/?$"
  );
  routes.push({ regex, paramNames, mountView, protected: isProtected, name: name || pattern });
}

function matchRoute(pathname) {
  for (const route of routes) {
    const m = route.regex.exec(pathname);
    if (m) {
      const params = {};
      route.paramNames.forEach((n, i) => (params[n] = decodeURIComponent(m[i + 1])));
      return { route, params };
    }
  }
  return null;
}

async function render(pathname) {
  const found = matchRoute(pathname);

  if (currentUnmount) {
    try {
      currentUnmount();
    } catch (err) {
      console.error("Erreur nettoyage vue précédente:", err);
    }
    currentUnmount = null;
  }

  if (!found) {
    console.warn("Route inconnue:", pathname);
    onRouteChange(null, {});
    return;
  }

  const { route, params } = found;

  if (route.protected && !isAuthenticated()) {
    onUnauthorized(pathname);
    return;
  }

  onRouteChange(route.name, params);

  const container = document.getElementById("main-content");
  container.innerHTML = LOADER_HTML;
  const result = await route.mountView(container, params);
  if (result && typeof result.unmount === "function") {
    currentUnmount = result.unmount;
  }
}

export function navigate(path, { replace = false } = {}) {
  const samePath = location.pathname === path;
  if (replace) {
    history.replaceState({}, "", path);
  } else if (!samePath) {
    history.pushState({}, "", path);
  }
  render(location.pathname);
}

export function start() {
  window.addEventListener("popstate", () => render(location.pathname));
  render(location.pathname);
}
