import { render as renderAccueil, title as titleAccueil, mount as mountAccueil } from "/marketing/views/accueil.js";
import { render as renderFonc, title as titleFonc } from "/marketing/views/fonctionnalite.js";
import { render as renderTarif, title as titleTarif } from "/marketing/views/tarif.js";

const ROUTES = {
  "/accueil": { render: renderAccueil, title: titleAccueil, mount: mountAccueil },
  "/": { render: renderAccueil, title: titleAccueil, mount: mountAccueil },
  "/fonctionnalite": { render: renderFonc, title: titleFonc },
  "/tarif": { render: renderTarif, title: titleTarif },
};

const root = document.getElementById("marketing-view");

function normalize(path) {
  path = path.replace(/\/$/, "");
  return path === "" ? "/accueil" : path;
}

function setActiveLink(path) {
  document.querySelectorAll(".nav-links a[data-route], .nav-plain-link[data-route]").forEach((a) => {
    a.classList.toggle("active-link", a.getAttribute("href") === path);
  });
}

let observer = null;
function observeReveals() {
  if (observer) observer.disconnect();
  observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("visible");
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12 });
  root.querySelectorAll(".reveal").forEach((el) => observer.observe(el));
}

let currentCleanup = null;

function renderRoute(path, { scroll = true } = {}) {
  if (typeof currentCleanup === "function") {
    try { currentCleanup(); } catch (err) { console.error(err); }
  }
  currentCleanup = null;

  const route = ROUTES[normalize(path)] || ROUTES["/accueil"];
  root.innerHTML = route.render();
  document.title = route.title;
  setActiveLink(normalize(path));
  observeReveals();
  if (typeof route.mount === "function") {
    const result = route.mount(root);
    if (typeof result === "function") currentCleanup = result;
  }
  if (scroll) window.scrollTo(0, 0);
}

function isInternalRoute(href) {
  try {
    const url = new URL(href, window.location.origin);
    if (url.origin !== window.location.origin) return false;
    return Object.prototype.hasOwnProperty.call(ROUTES, normalize(url.pathname));
  } catch {
    return false;
  }
}

// Intercepte tout lien interne vers une route connue (nav, footer, CTA
// dans le contenu des vues) - pas besoin d'un attribut dédié sur chaque
// lien, seul le chemin compte. Les liens vers /login, /signup, mailto:,
// pages légales etc. ne matchent aucune route et suivent leur navigation
// normale (pages séparées, volontairement hors de ce SPA). "#" (liens
// "à venir" du footer/des dropdowns de nav) est explicitement ignoré :
// sinon son pathname résout sur la page courante, qui matche souvent une
// route connue, et déclenche un renderRoute() inutile.
document.addEventListener("click", (e) => {
  const a = e.target.closest("a");
  if (!a) return;
  const href = a.getAttribute("href");
  if (!href || href === "#" || !isInternalRoute(href)) return;
  e.preventDefault();
  const url = new URL(href, window.location.origin);
  if (url.pathname !== window.location.pathname) {
    history.pushState({}, "", url.pathname);
  }
  renderRoute(url.pathname);
  const navLinks = document.querySelector(".nav-links");
  const hamburger = document.querySelector(".nav-hamburger");
  if (navLinks) navLinks.classList.remove("open");
  if (hamburger) hamburger.classList.remove("open");
});

window.addEventListener("popstate", () => renderRoute(window.location.pathname, { scroll: false }));

renderRoute(window.location.pathname);

const hamburger = document.querySelector(".nav-hamburger");
const navLinks = document.querySelector(".nav-links");
if (hamburger && navLinks) {
  hamburger.addEventListener("click", () => {
    navLinks.classList.toggle("open");
    hamburger.classList.toggle("open");
  });
}

// Dropdowns de nav ("Produits", "Ressources") : s'ouvrent au survol
// (clic toujours supporté, pour le tactile/clavier), un seul ouvert à la
// fois, fermeture avec un petit délai (pour tolérer le trajet de la
// souris entre le lien et le panneau) à la sortie, au clic en dehors,
// à l'Échap, ou en cliquant un lien du panneau.
const navDropdowns = Array.from(document.querySelectorAll(".nav-dropdown"));
const CLOSE_DELAY_MS = 150;
let closeTimeoutId = null;

// Floute le reste de la page (#marketing-view, footer) tant qu'un
// dropdown est ouvert - cf. règle CSS "body.nav-dropdown-open".
function syncNavDropdownBlur() {
  const anyOpen = navDropdowns.some((dropdown) => dropdown.classList.contains("is-open"));
  document.body.classList.toggle("nav-dropdown-open", anyOpen);
}

function cancelScheduledClose() {
  if (closeTimeoutId !== null) {
    clearTimeout(closeTimeoutId);
    closeTimeoutId = null;
  }
}

function openNavDropdown(dropdown, trigger, panel) {
  cancelScheduledClose();
  if (dropdown.classList.contains("is-open")) return;
  closeAllNavDropdowns();
  dropdown.classList.add("is-open");
  trigger.setAttribute("aria-expanded", "true");
  panel.hidden = false;
  syncNavDropdownBlur();
}

function closeNavDropdown(dropdown) {
  dropdown.classList.remove("is-open");
  dropdown.querySelector(".nav-dropdown-trigger")?.setAttribute("aria-expanded", "false");
  const panel = dropdown.querySelector(".nav-dropdown-panel");
  if (panel) panel.hidden = true;
  syncNavDropdownBlur();
}

function closeAllNavDropdowns() {
  navDropdowns.forEach(closeNavDropdown);
}

function scheduleClose(dropdown) {
  cancelScheduledClose();
  closeTimeoutId = setTimeout(() => {
    closeTimeoutId = null;
    closeNavDropdown(dropdown);
  }, CLOSE_DELAY_MS);
}

navDropdowns.forEach((dropdown) => {
  const trigger = dropdown.querySelector(".nav-dropdown-trigger");
  const panel = dropdown.querySelector(".nav-dropdown-panel");
  if (!trigger || !panel) return;

  trigger.addEventListener("mouseenter", () => openNavDropdown(dropdown, trigger, panel));
  panel.addEventListener("mouseenter", cancelScheduledClose);
  trigger.addEventListener("mouseleave", () => scheduleClose(dropdown));
  panel.addEventListener("mouseleave", () => scheduleClose(dropdown));

  trigger.addEventListener("click", () => {
    if (dropdown.classList.contains("is-open")) {
      cancelScheduledClose();
      closeNavDropdown(dropdown);
    } else {
      openNavDropdown(dropdown, trigger, panel);
    }
  });

  panel.addEventListener("click", (e) => {
    if (e.target.closest("a")) closeNavDropdown(dropdown);
  });
});

if (navDropdowns.length) {
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".nav-dropdown")) closeAllNavDropdowns();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeAllNavDropdowns();
  });
}

// Bouton "Dashboard" : le cookie de session est host-only sur
// api.xepay.finance (backend/auth.py, set_session_cookies - sans attribut
// Domain, donc envoyé au host ciblé par la requête quelle que soit
// l'origine de la page qui l'émet), et le CORS autorise déjà les
// requêtes avec credentials depuis www.xepay.finance (backend/main.py,
// allow_credentials=True). On peut donc vérifier la vraie session AVANT
// de naviguer et router directement vers le dashboard ou vers /login,
// sans jamais passer par dashboard.html entre les deux (plus de flash
// intermédiaire, contrairement au localStorage qui n'est lisible que sur
// l'origine qui l'a posé). Le href de base (marketing.html) reste
// optimiste (/dashboard.html) ; on ne le corrige que si besoin, une fois
// la réponse connue.
{
  const dashboardLink = document.querySelector('a[href="https://app.xepay.finance/dashboard.html"]');
  if (dashboardLink) {
    fetch("https://api.xepay.finance/me", { credentials: "include" })
      .then((res) => {
        if (!res.ok) dashboardLink.setAttribute("href", "/login");
      })
      .catch(() => {
        dashboardLink.setAttribute("href", "/login");
      });
  }
}
