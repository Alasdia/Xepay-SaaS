// Révélation en escalier du schéma en couches de la section architecture
// (Stripe -> Xepay -> Marchand -> Client du marchand), et succession
// dynamique des icônes dans le cadre "Moyens de paiement" (le défilement
// vertical du cadre commission est en CSS pur, voir marketing.css
// .xp-arch-commission-track). Ce module déclenche la classe "is-visible"
// une fois au scroll, puis pilote le remplacement périodique des icônes.

const ICON_POOL = [
  { icon: "mastercard", label: "Mastercard" },
  { icon: "visa", label: "Visa" },
  { icon: "apple-pay", label: "Apple Pay" },
  { icon: "google-pay", label: "Google Pay" },
  { icon: "cashapp", label: "Cash App" },
  { icon: "klarna-logo", label: "Klarna" },
  { icon: "bancontact", label: "Bancontact" },
  { icon: "ideal", label: "iDEAL" },
  { icon: "carte_bancaire", label: "Carte bancaire" },
  { icon: "link", label: "Link" },
];
const ICON_STEP_MS = 1700;
const ICON_FADE_MS = 220;

function mountIconSuccession(root, reduceMotion) {
  const frame = root.querySelector(".xp-arch-frame");
  const slots = frame ? Array.from(frame.querySelectorAll("img")) : [];
  if (!slots.length || reduceMotion) return () => {};

  let poolIndex = slots.length % ICON_POOL.length;
  let slotIndex = 0;
  let intervalId = null;
  const pendingTimeouts = new Set();

  function later(fn, ms) {
    const id = window.setTimeout(() => {
      pendingTimeouts.delete(id);
      fn();
    }, ms);
    pendingTimeouts.add(id);
  }

  function swapNext() {
    const slot = slots[slotIndex % slots.length];
    const next = ICON_POOL[poolIndex % ICON_POOL.length];
    slotIndex++;
    poolIndex++;
    slot.classList.add("is-swapping");
    later(() => {
      slot.src = `/assets/${next.icon}.svg`;
      slot.alt = next.label;
      slot.classList.remove("is-swapping");
    }, ICON_FADE_MS);
  }

  function start() {
    if (intervalId !== null) return;
    intervalId = window.setInterval(swapNext, ICON_STEP_MS);
  }
  function stop() {
    if (intervalId !== null) window.clearInterval(intervalId);
    intervalId = null;
  }

  const section = frame.closest(".arch-section") || frame;
  const observer = new IntersectionObserver((entries) => {
    const visible = entries.some((entry) => entry.isIntersecting);
    if (visible) start();
    else stop();
  }, { threshold: 0.3 });
  observer.observe(section);

  return function cleanup() {
    stop();
    observer.disconnect();
    pendingTimeouts.forEach((id) => window.clearTimeout(id));
    pendingTimeouts.clear();
  };
}

export function mountArchitecture(root) {
  const section = root.querySelector(".arch-section");
  if (!section) return () => {};

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const cleanupIcons = mountIconSuccession(root, reduceMotion);

  if (reduceMotion) {
    section.classList.add("is-visible");
    return cleanupIcons;
  }

  const observer = new IntersectionObserver((entries) => {
    const entry = entries[0];
    if (!entry || !entry.isIntersecting) return;
    section.classList.add("is-visible");
    observer.unobserve(section);
  }, { threshold: 0.3 });

  observer.observe(section);

  return function cleanup() {
    observer.disconnect();
    cleanupIcons();
  };
}
