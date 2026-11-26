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
function showSkeleton(container, routeName, params) {
  removeSkeleton();
  const overlay = document.createElement("div");
  overlay.id = SKELETON_OVERLAY_ID;
  const rect = container.getBoundingClientRect();
  overlay.style.top = `${rect.top}px`;
  overlay.style.left = `${rect.left}px`;
  overlay.style.width = `${rect.width}px`;
  overlay.innerHTML = getSkeleton(routeName, params);
  document.body.appendChild(overlay);
}

function removeSkeleton() {
  document.getElementById(SKELETON_OVERLAY_ID)?.remove();
}

// Écran de secours (demande du 2026-11-26) - affiché à la place d'une
// vue quand la navigation échoue pour une raison réseau (hors ligne
// détecté via navigator.onLine AVANT même d'essayer, ou setViewStyles/
// mountView qui rejette APRÈS coup, ex. le JS de la vue elle-même pas
// en cache). Styles posés en ligne (jamais une classe CSS externe) :
// c'est précisément le cas où aucun CSS externe n'est fiable. Couleur
// du site (#b45309) à 70% d'opacité sur "Réessayer", même convention
// que .shopify-tab--active (commerce.css).
function showOfflineFallback(container, pathname) {
  container.innerHTML = `
    <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; gap:14px; min-height:60vh; text-align:center; font-family:system-ui,-apple-system,sans-serif;">
      <div style="width:56px; height:56px; border-radius:16px; background:rgba(180,83,9,0.1); color:rgba(180,83,9,0.7); display:flex; align-items:center; justify-content:center; font-size:22px;">
        <i class="fa-solid fa-wifi" aria-hidden="true"></i>
      </div>
      <p style="margin:0; font-size:15px; font-weight:600; color:#111827;">Vous n'êtes pas connecté à Internet</p>
      <p style="margin:0; font-size:13px; color:#6b7280; max-width:360px;">Vérifiez votre connexion, puis réessayez.</p>
      <button type="button" id="spa-offline-retry-btn" style="margin-top:6px; background:transparent; border:1px solid rgba(180,83,9,0.7); color:rgba(180,83,9,0.7); border-radius:8px; padding:8px 18px; font-size:13.5px; font-weight:600; cursor:pointer;">Réessayer</button>
    </div>
  `;
  const btn = container.querySelector("#spa-offline-retry-btn");
  if (btn) btn.addEventListener("click", () => render(pathname));
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

  // Filet de sécurité : un tiroir de détails (shared/detailsDrawer.js)
  // laissé ouvert au moment de naviguer ailleurs ne se referme jamais lui-
  // même (son overlay disparaît avec le reste de #main-content, mais ses
  // effets posés sur <body> - classes + --xepay-drawer-width - lui, non),
  // donnant l'impression que la vue suivante garde une marge "réservée" à
  // un tiroir qui n'existe plus. On les retire ici à chaque navigation,
  // peu importe quelle vue les avait posés.
  document.body.classList.remove("xepay-drawer-open", "xepay-drawer-instant");

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

  // Détecté AVANT même d'essayer (demande du 2026-11-26) : évite le
  // flash skeleton -> HTML non stylé que provoquait l'ancien
  // comportement de setViewStyles (voir styleLoader.js).
  if (!navigator.onLine) {
    showOfflineFallback(container, pathname);
    return;
  }

  showSkeleton(container, route.name, params);
  const skeletonStart = Date.now();

  // mountFailed (demande du 2026-11-26) : mountView() peut rejeter
  // (setViewStyles qui a réellement échoué - voir styleLoader.js - ou
  // le JS de la vue elle-même, s'il n'était pas déjà en cache) - jamais
  // laissé non rattrapé comme avant, sinon le router restait bloqué
  // avec le skeleton affiché indéfiniment au lieu de proposer de
  // réessayer.
  let mountFailed = false;
  const mountPromise = Promise.resolve(route.mountView(container, params)).catch((err) => {
    console.error("Erreur montage vue (hors ligne ?):", err);
    mountFailed = true;
  });
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

  if (mountFailed) {
    showOfflineFallback(container, pathname);
    return;
  }

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
  // Renvoie la promesse de render() (résolue une fois la nouvelle vue
  // montée) - les 20 appelants existants l'ignorent (fire-and-forget,
  // comportement inchangé), mais un appelant qui a besoin de savoir quand
  // la nouvelle vue est réellement prête (ex: masquer un overlay de
  // transition) peut désormais faire await navigate(...).
  return render(location.pathname);
}

export function start() {
  window.addEventListener("popstate", () => render(location.pathname));
  render(location.pathname);
}
