import { render as renderAccueil, title as titleAccueil } from "/marketing/views/accueil.js";
import { render as renderFonc, title as titleFonc } from "/marketing/views/fonctionnalite.js";
import { render as renderTarif, title as titleTarif } from "/marketing/views/tarif.js";

const ROUTES = {
  "/accueil": { render: renderAccueil, title: titleAccueil },
  "/": { render: renderAccueil, title: titleAccueil },
  "/fonctionnalite": { render: renderFonc, title: titleFonc },
  "/tarif": { render: renderTarif, title: titleTarif },
};

const root = document.getElementById("marketing-view");

function normalize(path) {
  path = path.replace(/\/$/, "");
  return path === "" ? "/accueil" : path;
}

function setActiveLink(path) {
  document.querySelectorAll(".nav-links a[data-route]").forEach((a) => {
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

function renderRoute(path, { scroll = true } = {}) {
  const route = ROUTES[normalize(path)] || ROUTES["/accueil"];
  root.innerHTML = route.render();
  document.title = route.title;
  setActiveLink(normalize(path));
  observeReveals();
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
// normale (pages séparées, volontairement hors de ce SPA).
document.addEventListener("click", (e) => {
  const a = e.target.closest("a");
  if (!a) return;
  const href = a.getAttribute("href");
  if (!href || !isInternalRoute(href)) return;
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
