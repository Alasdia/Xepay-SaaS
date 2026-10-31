// Bloc "Paiements confirmés instantanément" : succession cinématique de 5
// vraies captures de la page de paiement Stripe/Xepay (formulaire → carte
// sélectionnée → saisie des coordonnées bancaires de test → traitement →
// confirmation). Les captures 3/4 ont des champs VIDES ; le numéro de
// carte/expiration/CVC sont tapés en direct par-dessus (vrai effet de
// frappe, caractère par caractère). Un vrai curseur (flèche) apparaît
// directement au point cliqué pour chaque clic (Carte, puis Payer), fait
// un petit effet de clic, puis disparaît — il ne glisse pas sur tout
// l'écran. Même mécanique que les autres blocs (IntersectionObserver,
// prefers-reduced-motion, cleanup).

// Temps d'affichage de chaque étape, dans l'ordre du DOM — rythme posé :
// 0) page checkout, 1) clic sur Carte, 2) saisie des coordonnées,
// 3) clic sur Payer + ~1s de chargement, 4) popup de succès.
const STEP_DURATIONS_MS = [1800, 1400, 2400, 1000, 2800];
const TYPE_MS_PER_CHAR = 55;

const FIELDS = [
  { key: "number", text: "4242 4242 4242 4242" },
  { key: "expiry", text: "12 / 28" },
  { key: "cvc", text: "123" },
];

export function mountCheckoutDemo(root) {
  const body = root.querySelector("[data-xp-checkout-demo]");
  const steps = body ? Array.from(body.querySelectorAll(".hl-frame-step")) : [];
  const cursor = root.querySelector("[data-xp-checkout-cursor]");
  const typeEls = {};
  FIELDS.forEach((f) => {
    typeEls[f.key] = root.querySelector(`[data-xp-checkout-type="${f.key}"]`);
  });
  if (!body || steps.length < 2) return () => {};

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduceMotion) return () => {};

  let index = 0;
  let timeoutId = null;
  const pendingTimeouts = new Set();
  let running = false;

  function later(fn, ms) {
    const id = setTimeout(() => {
      pendingTimeouts.delete(id);
      fn();
    }, ms);
    pendingTimeouts.add(id);
  }
  function clearPending() {
    pendingTimeouts.forEach(clearTimeout);
    pendingTimeouts.clear();
  }
  function clearTyping() {
    Object.values(typeEls).forEach((el) => {
      if (!el) return;
      el.textContent = "";
      el.classList.remove("is-typing");
    });
  }

  function typeField(fieldIndex) {
    const field = FIELDS[fieldIndex];
    const el = field && typeEls[field.key];
    if (!field || !el) return;
    el.classList.add("is-typing");
    let charIndex = 0;
    function step() {
      charIndex++;
      el.textContent = field.text.slice(0, charIndex);
      if (charIndex < field.text.length) {
        later(step, TYPE_MS_PER_CHAR);
      } else {
        el.classList.remove("is-typing");
        if (fieldIndex + 1 < FIELDS.length) later(() => typeField(fieldIndex + 1), 220);
      }
    }
    step();
  }

  // Clic sur "Carte" (position par défaut du curseur, cf. CSS).
  function clickCarte() {
    if (!cursor) return;
    cursor.classList.remove("is-at-payer", "is-clicking", "is-visible");
    later(() => cursor.classList.add("is-visible"), 100);
    later(() => cursor.classList.add("is-clicking"), 400);
    later(() => cursor.classList.remove("is-clicking"), 550);
    later(() => cursor.classList.remove("is-visible"), 900);
  }

  // Clic sur "Payer" : le curseur se repositionne pendant qu'il est
  // invisible (pas de glissement visible), puis apparaît déjà sur place.
  function clickPayer() {
    if (!cursor) return;
    cursor.classList.remove("is-visible", "is-clicking");
    cursor.classList.add("is-at-payer");
    later(() => cursor.classList.add("is-visible"), 60);
    later(() => cursor.classList.add("is-clicking"), 260);
    later(() => cursor.classList.remove("is-clicking"), 410);
    later(() => cursor.classList.remove("is-visible"), 650);
  }

  function showStep(i) {
    steps.forEach((el, j) => el.classList.toggle("is-active", j === i));

    if (i === 1) clickCarte();
    else if (i === 3) clickPayer();

    if (i === 2) {
      clearTyping();
      typeField(0);
    } else if (i === 0 || i === 1 || i === 4) {
      // i === 4 (succès) : le popup flouté couvre cette zone, le texte tapé
      // (net, pas flouté) ne doit pas rester visible par-dessus/autour.
      clearTyping();
    }
    // i === 3 (traitement) : on garde le texte déjà tapé affiché, le
    // formulaire rempli reste visible derrière le bouton qui charge.
  }

  function scheduleNext() {
    const duration = STEP_DURATIONS_MS[index % STEP_DURATIONS_MS.length];
    timeoutId = setTimeout(() => {
      index = (index + 1) % steps.length;
      showStep(index);
      scheduleNext();
    }, duration);
  }

  function start() {
    if (running) return;
    running = true;
    scheduleNext();
  }
  function stop() {
    running = false;
    if (timeoutId !== null) clearTimeout(timeoutId);
    timeoutId = null;
    clearPending();
    clearTyping();
    if (cursor) cursor.classList.remove("is-visible", "is-clicking", "is-at-payer");
  }

  const observer = new IntersectionObserver((entries) => {
    const visible = entries.some((entry) => entry.isIntersecting);
    if (visible) start();
    else stop();
  }, { threshold: 0.3 });
  observer.observe(body);

  return function cleanup() {
    stop();
    observer.disconnect();
    index = 0;
    showStep(0);
  };
}
