// Visuel animé "Recevez les paiements de vos clients" sur l'accueil.
// Mise à l'échelle : la maquette (reçu + tableau de bord) est dessinée à
// taille fixe (.xp-payments-stage, 1100px de large — doit rester synchro
// avec la largeur CSS du même sélecteur) puis réduite via transform:scale().
// 1100px est la largeur max réelle de .gf-wide-card sur grand écran : le
// ratio ne dépasse donc jamais 1, et le visuel remplit toujours la largeur
// disponible (plus d'espace mort), le facteur étant recalculé par
// ResizeObserver à chaque largeur de conteneur.

const STAGE_WIDTH = 1100;
const STEP_MS = 3000;
const ROW_COUNT = 9;

// Événements hors Afrique (la table statique initiale couvre déjà
// l'UEMOA) : montre que les clients de Xepay viennent du monde entier,
// avec un moyen de paiement différent à chaque fois.
const EVENTS = [
  { initials: "SW", avatarClass: "xp-dash-avatar-1", name: "Sarah Williams", order: "#CMD-10587", date: "29 oct. 2026", country: "🇺🇸 US", amount: "150,00 USD", status: "conteste", method: { icon: "mastercard", label: "Mastercard" } },
  { initials: "LB", avatarClass: "xp-dash-avatar-2", name: "Lukas Becker", order: "#CMD-10602", date: "28 oct. 2026", country: "🇩🇪 DE", amount: "640,00 USD", status: "reussi", method: { icon: "klarna-logo", label: "Klarna" } },
  { initials: "HS", avatarClass: "xp-dash-avatar-3", name: "Haruto Sato", order: "#CMD-10619", date: "27 oct. 2026", country: "🇯🇵 JP", amount: "980,00 USD", status: "reussi", method: { icon: "visa", label: "Visa" } },
  { initials: "NV", avatarClass: "xp-dash-avatar-1", name: "Noor Van Dijck", order: "#CMD-10634", date: "26 oct. 2026", country: "🇧🇪 BE", amount: "210,00 USD", status: "reussi", method: { icon: "bancontact", label: "Bancontact" } },
  { initials: "CM", avatarClass: "xp-dash-avatar-2", name: "Carlos Mendes", order: "#CMD-10651", date: "25 oct. 2026", country: "🇧🇷 BR", amount: "320,00 USD", status: "conteste", method: { icon: "link", label: "Link" } },
  { initials: "EC", avatarClass: "xp-dash-avatar-3", name: "Emily Carter", order: "#CMD-10668", date: "24 oct. 2026", country: "🇬🇧 GB", amount: "455,00 USD", status: "reussi", method: { icon: "apple-pay", label: "Apple Pay" } },
  { initials: "JT", avatarClass: "xp-dash-avatar-1", name: "Jake Thompson", order: "#CMD-10682", date: "23 oct. 2026", country: "🇨🇦 CA", amount: "530,00 USD", status: "reussi", method: { icon: "google-pay", label: "Google Pay" } },
  { initials: "OB", avatarClass: "xp-dash-avatar-2", name: "Olivia Baker", order: "#CMD-10699", date: "22 oct. 2026", country: "🇦🇺 AU", amount: "190,00 USD", status: "reussi", method: { icon: "cashapp", label: "Cash App" } },
];

const STATUS_LABEL = { reussi: "Réussi", conteste: "Contesté" };

function rowHtml(event) {
  return `
    <span class="xp-dash-client">
      <span class="xp-dash-avatar ${event.avatarClass}">${event.initials}</span>
      <span class="xp-dash-client-info">
        <span class="xp-dash-client-name">${event.name}</span>
        <span class="xp-dash-client-date">${event.date}</span>
      </span>
    </span>
    <span class="xp-dash-country">${event.country}</span>
    <span class="xp-dash-amount">${event.amount}</span>
    <span class="xp-dash-method"><img src="/assets/${event.method.icon}.svg" alt="${event.method.label}"></span>
    <span class="xp-dash-status"><span class="xp-dash-status-badge xp-dash-status-badge--${event.status}">${STATUS_LABEL[event.status]}</span></span>
  `;
}

export function mountPayments(root) {
  const frame = root.querySelector(".xp-payments-frame");
  const stage = root.querySelector(".xp-payments-stage");
  const table = root.querySelector("[data-xp-dash-table]");
  const receiptEl = root.querySelector("[data-xp-receipt]");
  const receiptName = root.querySelector("[data-xp-receipt-name]");
  const receiptOrder = root.querySelector("[data-xp-receipt-order]");
  const receiptDate = root.querySelector("[data-xp-receipt-date]");
  const receiptMethodIcon = root.querySelector("[data-xp-receipt-method-icon]");
  const receiptMethodLabel = root.querySelector("[data-xp-receipt-method-label]");
  const receiptAmount = root.querySelector("[data-xp-receipt-amount]");
  const linkPath = root.querySelector("[data-xp-link-path]");
  const linkChevron = root.querySelector("[data-xp-link-chevron]");
  const dashCard = root.querySelector(".xp-dash");
  const flyer = root.querySelector("[data-xp-flyer]");
  const flyerIcon = root.querySelector("[data-xp-flyer-icon]");
  const flyerAmount = root.querySelector("[data-xp-flyer-amount]");
  if (!frame || !stage || !table || !receiptEl) return () => {};

  const initialRowsHtml = table.innerHTML;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // offsetHeight reflète la boîte non transformée (transform ne change pas
  // la mise en page) : on peut mesurer la hauteur naturelle même une fois
  // le scale appliqué.
  const naturalHeight = stage.offsetHeight || 260;
  frame.style.aspectRatio = `${STAGE_WIDTH} / ${naturalHeight}`;

  let currentScale = 1;
  function applyScale() {
    const containerWidth = frame.clientWidth || STAGE_WIDTH;
    currentScale = Math.min(1, containerWidth / STAGE_WIDTH);
    stage.style.setProperty("--xp-scale", String(currentScale));
  }

  applyScale();
  const resizeObserver = new ResizeObserver(applyScale);
  resizeObserver.observe(frame);

  // getBoundingClientRect() reflète le rendu visuel (donc le scale) ; on
  // divise par currentScale pour revenir aux coordonnées "naturelles" du
  // stage, celles dans lesquelles le <svg> (non transformé lui non plus)
  // dessine son tracé.
  function stagePoint(el, vAlign) {
    const r = el.getBoundingClientRect();
    const s = stage.getBoundingClientRect();
    const y = vAlign === "bottom" ? r.bottom : r.top + r.height / 2;
    return {
      x: (r.left - s.left + r.width / 2) / currentScale,
      y: (y - s.top) / currentScale,
    };
  }

  function stageX(clientX) {
    const s = stage.getBoundingClientRect();
    return (clientX - s.left) / currentScale;
  }

  // Connecteur "agrafe" en pointillés gris : descend depuis le reçu (pas
  // de segment horizontal collé à sa bordure basse), passe sous le reçu
  // ET la ligne (jamais à travers le tableau), puis remonte. Le chevron
  // final est un <path> dessiné à la main (pas un marker SVG, plus fiable
  // à faire apparaître) pointant vers la gauche, sur la ligne client.
  const LINK_DROP_GAP = 24;

  const FLYER_DURATION_MS = 700;
  let flyerRafId = null;

  // Fait glisser la pastille montant + moyen de paiement le long du
  // connecteur (début = sous le reçu, fin = chevron sur la ligne),
  // via getPointAtLength — donne l'impression qu'elle est "déposée"
  // sur la ligne du tableau au moment où elle arrive.
  function flyAlongPath(event) {
    if (!flyer || !linkPath) return;
    const totalLength = linkPath.getTotalLength();
    if (!totalLength) return;

    if (flyerIcon) {
      flyerIcon.src = `/assets/${event.method.icon}.svg`;
      flyerIcon.alt = event.method.label;
    }
    if (flyerAmount) flyerAmount.textContent = event.amount;

    if (flyerRafId !== null) cancelAnimationFrame(flyerRafId);
    const startTime = performance.now();
    flyer.style.opacity = "1";

    function step(now) {
      const t = Math.min(1, (now - startTime) / FLYER_DURATION_MS);
      const point = linkPath.getPointAtLength(t * totalLength);
      flyer.style.transform = `translate(${point.x}px, ${point.y}px) translate(-50%, -50%)`;
      if (t < 1) {
        flyerRafId = requestAnimationFrame(step);
      } else {
        flyerRafId = null;
        later(() => {
          flyer.style.opacity = "0";
        }, 150);
      }
    }
    flyerRafId = requestAnimationFrame(step);
  }

  function drawLink(targetRow, event) {
    if (!linkPath || !linkChevron || !dashCard) return;
    const avatar = targetRow.querySelector(".xp-dash-avatar");
    if (!avatar) return;
    const from = stagePoint(receiptEl, "bottom");
    const rowY = stagePoint(avatar, "center").y;
    const borderX = stageX(dashCard.getBoundingClientRect().right);
    const arrowX = borderX + 50;
    const bottomY = Math.max(from.y, rowY) + LINK_DROP_GAP;
    linkPath.setAttribute("d", `M${from.x},${from.y} V${bottomY} H${arrowX} V${rowY} H${borderX}`);
    linkChevron.setAttribute("d", `M${borderX + 4},${rowY - 3} L${borderX},${rowY} L${borderX + 4},${rowY + 3}`);

    // Recale la phase des pointillés (dash 6 / gap 5, cf. CSS) pour que
    // le tout dernier pointillé tombe exactement sur l'extrémité du
    // tracé : sinon le dernier pointillé atterrit en plein milieu d'un
    // "gap" et paraît décroché de la ligne / du chevron.
    const DASH = 6;
    const PERIOD = DASH + 5;
    const len = linkPath.getTotalLength();
    const phase = ((DASH / 2 - len) % PERIOD + PERIOD) % PERIOD;
    linkPath.style.strokeDashoffset = String(phase);

    linkPath.classList.remove("is-visible");
    linkChevron.classList.remove("is-visible");
    requestAnimationFrame(() =>
      requestAnimationFrame(() => {
        linkPath.classList.add("is-visible");
        linkChevron.classList.add("is-visible");
      })
    );
    later(() => {
      linkPath.classList.remove("is-visible");
      linkChevron.classList.remove("is-visible");
    }, 1800);

    flyAlongPath(event);
  }

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

  function pulseReceipt(event) {
    if (receiptName) receiptName.textContent = event.name;
    if (receiptOrder) receiptOrder.textContent = event.order;
    if (receiptDate) receiptDate.textContent = event.date;
    if (receiptMethodIcon) {
      receiptMethodIcon.src = `/assets/${event.method.icon}.svg`;
      receiptMethodIcon.alt = event.method.label;
    }
    if (receiptMethodLabel) receiptMethodLabel.textContent = event.method.label;
    if (receiptAmount) receiptAmount.textContent = event.amount;
    receiptEl.classList.add("is-pulsing");
    later(() => receiptEl.classList.remove("is-pulsing"), 900);
  }

  function pushRow(event) {
    const row = document.createElement("div");
    row.className = "xp-dash-row is-entering is-new";
    row.innerHTML = rowHtml(event);
    table.insertBefore(row, table.children[1] || null);

    requestAnimationFrame(() => requestAnimationFrame(() => row.classList.remove("is-entering")));
    later(() => row.classList.remove("is-new"), 900);
    drawLink(row, event);

    const rows = Array.from(table.querySelectorAll(".xp-dash-row"));
    rows.slice(ROW_COUNT).forEach((old) => {
      old.classList.add("is-leaving");
      later(() => old.remove(), 320);
    });
  }

  function tick() {
    const event = EVENTS[eventIndex % EVENTS.length];
    eventIndex++;
    pulseReceipt(event);
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

  const initialRect = frame.getBoundingClientRect();
  const initiallyVisible = initialRect.bottom > 0 && initialRect.top < window.innerHeight;
  if (initiallyVisible) start();

  const intersectionObserver = new IntersectionObserver((entries) => {
    const visible = entries.some((entry) => entry.isIntersecting);
    if (visible) start();
    else stop();
  }, { threshold: 0.3 });
  intersectionObserver.observe(frame);

  return function cleanup() {
    stop();
    resizeObserver.disconnect();
    intersectionObserver.disconnect();
    pendingTimeouts.forEach(clearTimeout);
    pendingTimeouts.clear();
    table.innerHTML = initialRowsHtml;
    receiptEl.classList.remove("is-pulsing");
    if (linkPath) {
      linkPath.classList.remove("is-visible");
      linkPath.setAttribute("d", "");
    }
    if (linkChevron) {
      linkChevron.classList.remove("is-visible");
      linkChevron.setAttribute("d", "");
    }
    if (flyerRafId !== null) {
      cancelAnimationFrame(flyerRafId);
      flyerRafId = null;
    }
    if (flyer) flyer.style.opacity = "0";
  };
}
