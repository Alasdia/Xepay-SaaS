import { getSkeleton } from "./skeletons.js";

// Router maison — history.pushState/popstate, sans dépendance externe.
// Chaque route associe un pattern de path (params :nommés) à une fonction
// mountView(container, params) qui doit retourner { unmount() } (ou rien).
// Le router se charge d'appeler unmount() de la vue précédente avant de
// monter la suivante, et gère les routes protégées (redirection login).

// Skeleton de navigation commun aux 7 vues (structure propre à chaque vue :
// core/skeletons.js, styles : skeleton.css chargé en permanence par le
// shell). Chaque vue écrit elle-même son HTML final dans #main-content dès
// que son CSS est chargé (voir core/styleLoader.js) — un skeleton inséré
// DANS #main-content serait donc écrasé par cette même écriture avant la fin
// de la durée minimale voulue. Il est donc rendu à part, en position:fixed,
// calé en JS sur le rect réel de #main-content (jamais sur la sidebar, quel
// que soit le breakpoint), puis entièrement supprimé du DOM une fois la vue
// montée ET la durée minimale écoulée.
const SKELETON_OVERLAY_ID = "spa-nav-loader-overlay";

// Durée minimale d'affichage du skeleton pour éviter un flash instantané.
const MIN_SKELETON_MS = 1800;
// Garde-fou global : si mountView() reste bloqué (au-delà du timeout déjà
// géré par setViewStyles côté CSS), on ne bloque jamais indéfiniment le
// router — la vue précédente ou le skeleton restent affichés au pire.
const MOUNT_SAFETY_TIMEOUT_MS = 8000;

// Calé sur le rect réel de #main-content (jamais un left/width figé) afin
// de ne jamais recouvrir la sidebar, y compris sous le breakpoint mobile où
// #main-content perd son margin-left.
function showSkeleton(container, routeName) {
  removeSkeleton();
  const overlay = document.createElement("div");
  overlay.id = SKELETON_OVERLAY_ID;
  const rect = container.getBoundingClientRect();
  overlay.style.top = `${rect.top}px`;
  overlay.style.left = `${rect.left}px`;
  overlay.style.width = `${rect.width}px`;
  overlay.innerHTML = getSkeleton(routeName);
  document.body.appendChild(overlay);
}

function removeSkeleton() {
  document.getElementById(SKELETON_OVERLAY_ID)?.remove();
}

const routes = [];
let currentUnmount = null;
let navToken = 0;
let isAuthenticated = () => true;
let onUnauthorized = () => {
  window.location.href = "/login";
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
  showSkeleton(container, route.name);
  const skeletonStart = Date.now();

  const mountPromise = Promise.resolve(route.mountView(container, params));
  const safetyTimeout = new Promise((resolve) => setTimeout(resolve, MOUNT_SAFETY_TIMEOUT_MS));
  const result = await Promise.race([mountPromise, safetyTimeout]);

  const elapsed = Date.now() - skeletonStart;
  if (elapsed < MIN_SKELETON_MS) {
    await new Promise((resolve) => setTimeout(resolve, MIN_SKELETON_MS - elapsed));
  }

  // Navigation dépassée par une navigation plus récente pendant l'attente :
  // ne pas retirer son skeleton ni écraser son currentUnmount avec le nôtre.
  if (myToken !== navToken) return;

  removeSkeleton();
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
