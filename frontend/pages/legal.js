// Nav partagée (hamburger mobile + dropdowns "Produits"/"Ressources") :
// ces pages légales sont des pages statiques hors du routeur SPA
// (marketing/router.js), donc elles ne chargent pas ce script-là — on
// réimplémente ici juste l'interaction de nav, identique à celle du SPA.
const hamburger = document.querySelector('.nav-hamburger');
const navLinks = document.querySelector('.nav-links');
if (hamburger && navLinks) {
  hamburger.addEventListener('click', () => {
    navLinks.classList.toggle('open');
    hamburger.classList.toggle('open');
  });
}

const navDropdowns = Array.from(document.querySelectorAll('.nav-dropdown'));
const CLOSE_DELAY_MS = 150;
let closeTimeoutId = null;

function cancelScheduledClose() {
  if (closeTimeoutId !== null) {
    clearTimeout(closeTimeoutId);
    closeTimeoutId = null;
  }
}

function closeNavDropdown(dropdown) {
  dropdown.classList.remove('is-open');
  dropdown.querySelector('.nav-dropdown-trigger')?.setAttribute('aria-expanded', 'false');
  const panel = dropdown.querySelector('.nav-dropdown-panel');
  if (panel) panel.hidden = true;
}

function closeAllNavDropdowns() {
  navDropdowns.forEach(closeNavDropdown);
}

function openNavDropdown(dropdown, trigger, panel) {
  cancelScheduledClose();
  if (dropdown.classList.contains('is-open')) return;
  closeAllNavDropdowns();
  dropdown.classList.add('is-open');
  trigger.setAttribute('aria-expanded', 'true');
  panel.hidden = false;
}

function scheduleClose(dropdown) {
  cancelScheduledClose();
  closeTimeoutId = setTimeout(() => {
    closeTimeoutId = null;
    closeNavDropdown(dropdown);
  }, CLOSE_DELAY_MS);
}

navDropdowns.forEach((dropdown) => {
  const trigger = dropdown.querySelector('.nav-dropdown-trigger');
  const panel = dropdown.querySelector('.nav-dropdown-panel');
  if (!trigger || !panel) return;

  trigger.addEventListener('mouseenter', () => openNavDropdown(dropdown, trigger, panel));
  panel.addEventListener('mouseenter', cancelScheduledClose);
  trigger.addEventListener('mouseleave', () => scheduleClose(dropdown));
  panel.addEventListener('mouseleave', () => scheduleClose(dropdown));

  trigger.addEventListener('click', () => {
    if (dropdown.classList.contains('is-open')) {
      cancelScheduledClose();
      closeNavDropdown(dropdown);
    } else {
      openNavDropdown(dropdown, trigger, panel);
    }
  });

  panel.addEventListener('click', (e) => {
    if (e.target.closest('a')) closeNavDropdown(dropdown);
  });
});

if (navDropdowns.length) {
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.nav-dropdown')) closeAllNavDropdowns();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeAllNavDropdowns();
  });
}

// Lien "Dashboard" : redirige vers /login si le visiteur n'a pas de
// session active, comme sur les autres pages marketing (cf.
// marketing/router.js) — le cookie de session est vérifié auprès de
// l'API avant de laisser le lien pointer vers le dashboard.
{
  const dashboardLink = document.querySelector('a[href="https://app.xepay.finance/dash/workspace/me/"]');
  if (dashboardLink) {
    fetch('https://api.xepay.finance/me', { credentials: 'include' })
      .then((res) => {
        if (!res.ok) dashboardLink.setAttribute('href', '/login');
      })
      .catch(() => {
        dashboardLink.setAttribute('href', '/login');
      });
  }
}

// Sommaire : défilement doux + surbrillance de la section active.
const tocLinks = document.querySelectorAll('.legal-toc a');
const sections = Array.from(tocLinks).map((a) => document.querySelector(a.getAttribute('href')));
tocLinks.forEach((a) => {
  a.addEventListener('click', (e) => {
    e.preventDefault();
    const target = document.querySelector(a.getAttribute('href'));
    if (target) target.scrollIntoView({ behavior: 'smooth' });
  });
});
const tocObserver = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    const link = document.querySelector(`.legal-toc a[href="#${entry.target.id}"]`);
    if (!link) return;
    if (entry.isIntersecting) {
      tocLinks.forEach((a) => a.classList.remove('active'));
      link.classList.add('active');
    }
  });
}, { rootMargin: '-110px 0px -70% 0px' });
sections.forEach((s) => { if (s) tocObserver.observe(s); });
