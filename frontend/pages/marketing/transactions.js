// Suivi des transactions en temps réel (bloc vertical "Suivez vos
// transactions en direct"). Même mécanique d'animation que payments.js
// (tick périodique, IntersectionObserver, prefers-reduced-motion,
// cleanup) mais sans mise à l'échelle : ce tableau est déjà assez étroit
// pour rester fluide (colonnes en fr) dans sa colonne de grille.

const STEP_MS = 3000;
const ROW_COUNT = 5;

// Paliers réels de backend/services/commission_service.py (COMMISSION_TIERS) —
// pas un taux fixe. Le taux appliqué à une transaction dépend du volume déjà
// encaissé par le marchand CE mois-ci avant elle ; chaque événement porte
// donc son propre "cumulativeBefore" plausible plutôt qu'un taux en dur.
const COMMISSION_TIERS = [
  [0, 0.06],
  [5000, 0.05],
  [20000, 0.04],
  [75000, 0.03],
];

function resolveCommissionRate(volumeBefore) {
  let rate = COMMISSION_TIERS[0][1];
  for (const [threshold, tierRate] of COMMISSION_TIERS) {
    if (volumeBefore >= threshold) rate = tierRate;
  }
  return rate;
}

const EVENTS = [
  { name: "Aminata Diallo", method: { icon: "klarna-logo", label: "Klarna" }, amount: 540, cumulativeBefore: 3200 },
  { name: "John Walker", method: { icon: "link", label: "Link" }, amount: 275, cumulativeBefore: 3740 },
  { name: "Sophie Laurent", method: { icon: "bancontact", label: "Bancontact" }, amount: 890, cumulativeBefore: 4015 },
  { name: "Kwame Asante", method: { icon: "carte_bancaire", label: "Carte bancaire" }, amount: 150, cumulativeBefore: 6200 },
  { name: "Laura Fischer", method: { icon: "ideal", label: "iDEAL" }, amount: 430, cumulativeBefore: 8500 },
];

function formatUSD(amount) {
  return `${amount.toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USD`;
}

function rowHtml(event) {
  const rate = resolveCommissionRate(event.cumulativeBefore);
  const fee = event.amount * rate;
  const net = event.amount - fee;
  return `
    <span class="xp-txns-client">${event.name}</span>
    <span class="xp-txns-method"><img src="/assets/${event.method.icon}.svg" alt="${event.method.label}"></span>
    <span class="xp-txns-amount">${formatUSD(event.amount)}</span>
    <span class="xp-txns-fee">${formatUSD(fee)}</span>
    <span class="xp-txns-net">${formatUSD(net)}</span>
  `;
}

export function mountTransactions(root) {
  const table = root.querySelector("[data-xp-txns-table]");
  if (!table) return () => {};

  const section = table.closest(".gf-vertical-txns") || table;
  const initialRowsHtml = table.innerHTML;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  let eventIndex = 0;
  let intervalId = null;
  const pendingTimeouts = new Set();

  function later(fn, ms) {
    const id = setTimeout(() => {
      pendingTimeouts.delete(id);
      fn();
    }, ms);
    pendingTimeouts.add(id);
    return id;
  }

  function pushRow(event) {
    const row = document.createElement("div");
    row.className = "xp-txns-row is-entering is-new";
    row.innerHTML = rowHtml(event);
    table.insertBefore(row, table.children[1] || null);

    requestAnimationFrame(() => requestAnimationFrame(() => row.classList.remove("is-entering")));
    later(() => row.classList.remove("is-new"), 900);

    const rows = Array.from(table.querySelectorAll(".xp-txns-row"));
    rows.slice(ROW_COUNT).forEach((old) => {
      old.classList.add("is-leaving");
      later(() => old.remove(), 320);
    });
  }

  function tick() {
    const event = EVENTS[eventIndex % EVENTS.length];
    eventIndex++;
    pushRow(event);
  }

  function start() {
    if (intervalId !== null || reduceMotion) return;
    intervalId = setInterval(tick, STEP_MS);
  }
  function stop() {
    if (intervalId !== null) clearInterval(intervalId);
    intervalId = null;
  }

  const initialRect = section.getBoundingClientRect();
  const initiallyVisible = initialRect.bottom > 0 && initialRect.top < window.innerHeight;
  if (initiallyVisible) start();

  const intersectionObserver = new IntersectionObserver((entries) => {
    const visible = entries.some((entry) => entry.isIntersecting);
    if (visible) start();
    else stop();
  }, { threshold: 0.3 });
  intersectionObserver.observe(section);

  return function cleanup() {
    stop();
    intersectionObserver.disconnect();
    pendingTimeouts.forEach(clearTimeout);
    pendingTimeouts.clear();
    table.innerHTML = initialRowsHtml;
  };
}
