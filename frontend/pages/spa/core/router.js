// Router maison — history.pushState/popstate, sans dépendance externe.
// Chaque route associe un pattern de path (params :nommés) à une fonction
// mountView(container, params) qui doit retourner { unmount() } (ou rien).
// Le router se charge d'appeler unmount() de la vue précédente avant de
// monter la suivante, et gère les routes protégées (redirection login).

// Loader commun aux 7 vues. Chaque vue écrit elle-même son HTML final dans
// #main-content dès que son CSS est chargé (voir core/styleLoader.js) — un
// loader inséré DANS #main-content serait donc écrasé par cette même
// écriture avant la fin de la durée minimale voulue. Il est donc rendu à
// part, en position:fixed, calé en JS sur le rect réel de #main-content
// (jamais sur la sidebar, quel que soit le breakpoint), et retiré seulement
// une fois la vue montée ET la durée minimale écoulée.
const LOADER_OVERLAY_ID = "spa-nav-loader-overlay";
const LOADER_OVERLAY_HTML = `
<div class="spinner-border" role="status" style="width:1.5rem;height:1.5rem;border-width:.2em;color:#facc15;">
  <span class="visually-hidden">Chargement...</span>
</div>
`;

// Durée minimale d'affichage du loader pour éviter un flash instantané.
const MIN_LOADER_MS = 2000;
// Garde-fou global : si mountView() reste bloqué (au-delà du timeout déjà
// géré par setViewStyles côté CSS), on ne bloque jamais indéfiniment le
// router — la vue précédente ou le loader restent affichés au pire.
const MOUNT_SAFETY_TIMEOUT_MS = 8000;

function getLoaderOverlay() {
  let overlay = document.getElementById(LOADER_OVERLAY_ID);
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.id = LOADER_OVERLAY_ID;
    overlay.style.position = "fixed";
    overlay.style.bottom = "0";
    overlay.style.display = "flex";
    overlay.style.alignItems = "center";
    overlay.style.justifyContent = "center";
    overlay.style.background = "#ffffff";
    overlay.style.zIndex = "400";
    overlay.innerHTML = LOADER_OVERLAY_HTML;
    document.body.appendChild(overlay);
  }
  return overlay;
}

// Calé sur le rect réel de #main-content (jamais un left/width figé) afin
// de ne jamais recouvrir la sidebar, y compris sous le breakpoint mobile où
// #main-content perd son margin-left.
function showLoaderOverlay(container) {
  const overlay = getLoaderOverlay();
  const rect = container.getBoundingClientRect();
  overlay.style.top = `${rect.top}px`;
  overlay.style.left = `${rect.left}px`;
  overlay.style.width = `${rect.width}px`;
  overlay.style.display = "flex";
}

function hideLoaderOverlay() {
  const overlay = document.getElementById(LOADER_OVERLAY_ID);
  if (overlay) overlay.style.display = "none";
}

const routes = [];
let currentUnmount = null;
let navToken = 0;
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

  const myToken = ++navToken;
  const container = document.getElementById("main-content");
  showLoaderOverlay(container);
  const loaderStart = Date.now();

  const mountPromise = Promise.resolve(route.mountView(container, params));
  const safetyTimeout = new Promise((resolve) => setTimeout(resolve, MOUNT_SAFETY_TIMEOUT_MS));
  const result = await Promise.race([mountPromise, safetyTimeout]);

  const elapsed = Date.now() - loaderStart;
  if (elapsed < MIN_LOADER_MS) {
    await new Promise((resolve) => setTimeout(resolve, MIN_LOADER_MS - elapsed));
  }

  // Navigation dépassée par une navigation plus récente pendant l'attente :
  // ne pas masquer son overlay ni écraser son currentUnmount avec le nôtre.
  if (myToken !== navToken) return;

  hideLoaderOverlay();
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
