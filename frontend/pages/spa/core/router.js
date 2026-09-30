// Router maison — history.pushState/popstate, sans dépendance externe.
// Chaque route associe un pattern de path (params :nommés) à une fonction
// mountView(container, params) qui doit retourner { unmount() } (ou rien).
// Le router se charge d'appeler unmount() de la vue précédente avant de
// monter la suivante, et gère les routes protégées (redirection login).

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
