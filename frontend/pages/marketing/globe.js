// Globe animé de la section "Le monde paie." sur l'accueil.
// Canvas 2D (aucune dépendance), sphère de points Fibonacci filtrés sur des
// continents approximatifs, arcs de paiement vers l'Afrique de l'Ouest.

const TAU = Math.PI * 2;
const toRad = (deg) => (deg * Math.PI) / 180;

// Polygones lat/lon simplifiés par masse continentale (coordonnées [lon, lat]),
// détaillés juste assez pour que les points retenus dessinent des silhouettes
// de continents reconnaissables plutôt que des blobs.
const LANDMASSES = [
  // Afrique
  [[-9, 35.7], [-5.5, 36], [10, 37], [19, 32.5], [25, 31.5], [34, 31.5], [35, 27], [43, 13], [51, 12], [51, 10],
   [45, 2], [41, -2], [40, -10], [35, -18], [35, -24], [32, -29], [27, -33.5], [20, -34.8], [18, -34.4], [13, -27],
   [12, -18], [12, -5], [9, 2], [8.5, 4.5], [3, 6.5], [-1, 5], [-3, 5], [-7.5, 4.5], [-11, 7], [-13, 9],
   [-16.5, 12.5], [-17.5, 14.7], [-17, 21], [-13, 27.5]],
  // Europe continentale
  [[-9, 37], [-9, 43], [-1, 49], [3, 51], [9, 54], [9, 57], [10, 63], [16, 68], [25, 70], [30, 70], [35, 66],
   [40, 56], [38, 48], [34, 45], [28, 41], [23, 37], [17, 40], [12, 38], [15, 41], [9, 41], [9, 38], [2, 41],
   [-5, 36]],
  // Îles britanniques
  [[-10, 50], [-6, 50], [-3, 56], [-6, 58], [-9, 54]],
  // Asie
  [[35, 38], [45, 40], [48, 42], [55, 42], [60, 45], [60, 55], [65, 68], [75, 72], [90, 73], [110, 73], [140, 73],
   [160, 68], [163, 60], [155, 52], [142, 45], [132, 42], [128, 38], [122, 34], [122, 30], [117, 24], [109, 18],
   [106, 10], [103, 2], [97, 5], [92, 15], [88, 22], [80, 18], [77, 8], [73, 16], [68, 24], [61, 25], [57, 27],
   [55, 27], [50, 15], [44, 12], [42, 16], [35, 28], [34, 32]],
  // Japon
  [[130, 31], [132, 34], [137, 35], [140, 36], [141, 40], [143, 43], [141, 45], [139, 41], [135, 35]],
  // Indonésie / péninsule malaise (bloc simplifié)
  [[95, 5], [106, -6], [115, -8], [119, -3], [117, 1], [109, 2], [99, 3]],
  // Philippines
  [[120, 18], [122, 14], [126, 9], [122, 6], [119, 10]],
  // Australie
  [[113, -22], [122, -18], [130, -12], [137, -12], [142, -11], [145, -16], [146, -19], [153, -28], [150, -34],
   [147, -38], [140, -38], [136, -35], [132, -32], [129, -31], [122, -34], [115, -34], [113, -28]],
  // Amérique du Nord
  [[-168, 66], [-165, 70], [-150, 70], [-130, 70], [-110, 68], [-95, 68], [-85, 62], [-80, 55], [-65, 50],
   [-60, 47], [-67, 45], [-70, 42], [-74, 40], [-76, 36], [-80, 32], [-81, 25], [-83, 25], [-88, 30], [-90, 29],
   [-94, 29], [-97, 26], [-97, 20], [-91, 16], [-93, 16], [-105, 21], [-110, 24], [-115, 28], [-117, 32],
   [-122, 37], [-124, 40], [-124, 46], [-124, 48], [-130, 55], [-140, 60], [-152, 60], [-162, 60]],
  // Groenland
  [[-45, 60], [-20, 70], [-20, 82], [-55, 82], [-73, 78], [-55, 60]],
  // Amérique du Sud
  [[-77, 8], [-72, 11], [-66, 10], [-62, 10], [-58, 7], [-51, 0], [-48, -5], [-35, -5], [-35, -10], [-38, -13],
   [-39, -17], [-41, -20], [-43, -23], [-48, -26], [-53, -29], [-57, -34], [-62, -39], [-65, -43], [-68, -49],
   [-70, -52], [-73, -53], [-72, -48], [-71, -45], [-71, -39], [-71, -33], [-71, -25], [-75, -15], [-78, -8],
   [-80, -5], [-79, -2]],
  // Madagascar
  [[43, -12], [50, -16], [47, -25], [44, -22]],
];

function pointInPolygon(lon, lat, poly) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i];
    const [xj, yj] = poly[j];
    if ((yi > lat) !== (yj > lat) && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) {
      inside = !inside;
    }
  }
  return inside;
}

function isLand(lon, lat) {
  return LANDMASSES.some((poly) => pointInPolygon(lon, lat, poly));
}

function fibonacciLandPoints(count) {
  const golden = Math.PI * (3 - Math.sqrt(5));
  const points = [];
  for (let i = 0; i < count; i++) {
    const y = 1 - (i / (count - 1)) * 2;
    const theta = golden * i;
    const radius = Math.sqrt(Math.max(0, 1 - y * y));
    const x = Math.cos(theta) * radius;
    const z = Math.sin(theta) * radius;
    const lat = (Math.asin(y) * 180) / Math.PI;
    const lon = (Math.atan2(z, x) * 180) / Math.PI;
    if (isLand(lon, lat)) points.push({ lat, lon });
  }
  return points;
}

function latLonToVec3(lat, lon) {
  const latR = toRad(lat);
  const lonR = toRad(lon);
  return [Math.cos(latR) * Math.sin(lonR), Math.sin(latR), Math.cos(latR) * Math.cos(lonR)];
}

// Rotation vue : yaw amène `lonDeg` face caméra, pitch amène `latDeg` face caméra.
function rotateVec([x, y, z], lonDeg, latDeg) {
  const a = -toRad(lonDeg);
  const b = toRad(latDeg);
  const x1 = x * Math.cos(a) + z * Math.sin(a);
  const z1 = -x * Math.sin(a) + z * Math.cos(a);
  const y2 = y * Math.cos(b) - z1 * Math.sin(b);
  const z2 = y * Math.sin(b) + z1 * Math.cos(b);
  return [x1, y2, z2];
}

function slerp(v0, v1, t) {
  const dot = Math.max(-1, Math.min(1, v0[0] * v1[0] + v0[1] * v1[1] + v0[2] * v1[2]));
  const omega = Math.acos(dot);
  if (omega < 1e-6) return v0;
  const s0 = Math.sin((1 - t) * omega) / Math.sin(omega);
  const s1 = Math.sin(t * omega) / Math.sin(omega);
  return [v0[0] * s0 + v1[0] * s1, v0[1] * s0 + v1[1] * s1, v0[2] * s0 + v1[2] * s1];
}

function hexToRgb(hex) {
  const n = parseInt(hex.replace("#", ""), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function mixRgb(a, b, t) {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
}

function rgba([r, g, b], a) {
  return `rgba(${r | 0},${g | 0},${b | 0},${a})`;
}

// Lumière fixe (en espace caméra, après rotation) : donne un vrai
// terminator jour/nuit sur le globe plutôt qu'un simple fondu par
// profondeur caméra — c'est ça qui manquait de réalisme.
function normalize3([x, y, z]) {
  const len = Math.sqrt(x * x + y * y + z * z) || 1;
  return [x / len, y / len, z / len];
}
const LIGHT = normalize3([0.45, 0.55, 0.75]);

// Villes et montants de démonstration pour les arcs de paiement — pas de données réelles.
const DESTINATIONS = {
  abidjan: { lat: 5.3, lon: -4.0 },
  dakar: { lat: 14.7, lon: -17.4 },
  bamako: { lat: 12.65, lon: -8.0 },
  ouaga: { lat: 12.37, lon: -1.52 },
  cotonou: { lat: 6.37, lon: 2.43 },
  lome: { lat: 6.13, lon: 1.22 },
  niamey: { lat: 13.51, lon: 2.13 },
};

// Icônes réelles (/assets) pour les étiquettes de montant, cyclées par arc.
const PAYMENT_METHODS = ["visa", "mastercard", "apple-pay", "google-pay", "cashapp"];

// Le monde entier paie (origines USD + EUR, tous continents), l'Afrique de
// l'Ouest encaisse (les 7 destinations déjà définies ci-dessus) : un flux
// dense plutôt que quelques routes isolées.
const ORIGINS = [
  // Amérique du Nord (USA + Canada + Mexique) — USD
  { lat: 40.7, lon: -74.0, currency: "USD" },
  { lat: 34.05, lon: -118.24, currency: "USD" },
  { lat: 41.88, lon: -87.63, currency: "USD" },
  { lat: 29.76, lon: -95.37, currency: "USD" },
  { lat: 47.6, lon: -122.33, currency: "USD" },
  { lat: 25.76, lon: -80.19, currency: "USD" },
  { lat: 42.36, lon: -71.06, currency: "USD" },
  { lat: 38.9, lon: -77.04, currency: "USD" },
  { lat: 43.7, lon: -79.4, currency: "USD" },
  { lat: 45.5, lon: -73.6, currency: "USD" },
  { lat: 49.28, lon: -123.12, currency: "USD" },
  { lat: 19.4, lon: -99.13, currency: "USD" },
  // Amérique du Sud — USD
  { lat: -23.55, lon: -46.63, currency: "USD" },
  { lat: -34.6, lon: -58.4, currency: "USD" },
  { lat: 4.71, lon: -74.07, currency: "USD" },
  { lat: -12.05, lon: -77.04, currency: "USD" },
  { lat: -33.45, lon: -70.67, currency: "USD" },
  // Europe — EUR
  { lat: 51.5, lon: -0.1, currency: "EUR" },
  { lat: 48.85, lon: 2.35, currency: "EUR" },
  { lat: 52.52, lon: 13.4, currency: "EUR" },
  { lat: 40.42, lon: -3.7, currency: "EUR" },
  { lat: 41.9, lon: 12.5, currency: "EUR" },
  { lat: 52.37, lon: 4.9, currency: "EUR" },
  { lat: 50.85, lon: 4.35, currency: "EUR" },
  { lat: 47.37, lon: 8.55, currency: "EUR" },
  { lat: 38.72, lon: -9.14, currency: "EUR" },
  { lat: 48.21, lon: 16.37, currency: "EUR" },
  { lat: 59.33, lon: 18.06, currency: "EUR" },
  { lat: 52.23, lon: 21.01, currency: "EUR" },
  { lat: 53.35, lon: -6.26, currency: "EUR" },
  { lat: 55.68, lon: 12.57, currency: "EUR" },
  // Asie — USD
  { lat: 25.2, lon: 55.3, currency: "USD" },
  { lat: 1.35, lon: 103.82, currency: "USD" },
  { lat: 35.68, lon: 139.7, currency: "USD" },
  { lat: 22.3, lon: 114.17, currency: "USD" },
  { lat: 19.08, lon: 72.88, currency: "USD" },
  { lat: 37.57, lon: 127.0, currency: "USD" },
  { lat: 13.76, lon: 100.5, currency: "USD" },
  { lat: 31.23, lon: 121.47, currency: "USD" },
  { lat: 39.9, lon: 116.4, currency: "USD" },
  { lat: -6.2, lon: 106.85, currency: "USD" },
  { lat: 14.6, lon: 120.98, currency: "USD" },
  // Océanie — USD (peu visible sous cet angle de caméra, gardé malgré tout)
  { lat: -33.87, lon: 151.2, currency: "USD" },
];

const ARC_AMOUNTS = [
  720, 540, 310, 980, 450, 275, 615, 890, 360, 725, 195, 830, 410, 560, 920,
  680, 250, 770, 505, 640, 385, 860, 295, 705, 470,
];

const DESTINATION_LIST = Object.values(DESTINATIONS);

const ARC_ROUTES = ORIGINS.map((origin, i) => {
  const amount = ARC_AMOUNTS[i % ARC_AMOUNTS.length];
  const symbol = origin.currency === "EUR" ? "€" : "$";
  return {
    lat: origin.lat,
    lon: origin.lon,
    to: DESTINATION_LIST[i % DESTINATION_LIST.length],
    amount: `${symbol}${amount} ${origin.currency}`,
  };
});

const CENTER_LON = -6;
const CENTER_LAT = 10;
const DRAW_MS = 1400;
const HOLD_MS = 500;
const FADE_MS = 650;
const SPAWN_MS = 260;
const MAX_CONCURRENT_ARCS = 12;

export function mountGlobe(root) {
  const canvas = root.querySelector(".globe-canvas");
  const labelsEl = root.querySelector(".globe-labels");
  if (!canvas || !labelsEl) return () => {};

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const ctx = canvas.getContext("2d");
  const rootStyles = getComputedStyle(document.documentElement);
  const colorDeep = hexToRgb(rootStyles.getPropertyValue("--gold-deep").trim() || "#b45309");
  const colorGold = hexToRgb(rootStyles.getPropertyValue("--gold").trim() || "#f59e0b");
  const colorLight = hexToRgb(rootStyles.getPropertyValue("--gold-light").trim() || "#fbbf24");

  const landPoints = fibonacciLandPoints(9500).map((p) => ({ ...p, vec: latLonToVec3(p.lat, p.lon) }));

  function createLabel(methodIndex) {
    const method = PAYMENT_METHODS[methodIndex % PAYMENT_METHODS.length];
    const el = document.createElement("div");
    el.className = "globe-label";
    el.innerHTML = `<img src="/assets/${method}.svg" alt="" class="globe-label-icon"><span class="globe-label-amount"></span>`;
    el.style.opacity = "0";
    labelsEl.appendChild(el);
    return { el, amountEl: el.querySelector(".globe-label-amount") };
  }

  let cssWidth = 0;
  let cssHeight = 0;
  let cx = 0;
  let cy = 0;
  let radius = 0;

  function resize() {
    const rect = canvas.getBoundingClientRect();
    cssWidth = rect.width;
    cssHeight = rect.height;
    cx = cssWidth / 2;
    cy = cssHeight / 2;
    radius = Math.min(cssWidth, cssHeight) / 2 * 0.86;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(cssWidth * dpr);
    canvas.height = Math.round(cssHeight * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  const resizeObserver = new ResizeObserver(resize);
  resizeObserver.observe(canvas);
  resize();

  let dragLon = 0;
  let isDragging = false;
  let lastX = 0;

  // Survol (sans clic) : incline doucement le globe vers le curseur.
  // Pendant un drag explicite, le survol est neutralisé au profit de dragLon.
  let hoverLon = 0;
  let hoverLat = 0;
  let hoverTargetLon = 0;
  let hoverTargetLat = 0;
  const MAX_HOVER_LON = 42;
  const MAX_HOVER_LAT = 16;

  function updateHoverTarget(e) {
    const rect = canvas.getBoundingClientRect();
    const relX = (e.clientX - (rect.left + rect.width / 2)) / (rect.width / 2);
    const relY = (e.clientY - (rect.top + rect.height / 2)) / (rect.height / 2);
    hoverTargetLon = Math.max(-1, Math.min(1, relX)) * MAX_HOVER_LON;
    hoverTargetLat = -Math.max(-1, Math.min(1, relY)) * MAX_HOVER_LAT;
  }

  function onPointerDown(e) {
    isDragging = true;
    lastX = e.clientX;
    hoverTargetLon = 0;
    hoverTargetLat = 0;
    hoverLon = 0;
    hoverLat = 0;
    canvas.setPointerCapture(e.pointerId);
    canvas.classList.add("is-dragging");
  }
  function onPointerMove(e) {
    if (isDragging) {
      const dx = e.clientX - lastX;
      lastX = e.clientX;
      dragLon += dx * 0.25;
    } else {
      updateHoverTarget(e);
    }
    if (reduceMotion) {
      if (!isDragging) { hoverLon = hoverTargetLon; hoverLat = hoverTargetLat; }
      renderFrame(performance.now());
    }
  }
  function onPointerUp(e) {
    isDragging = false;
    canvas.classList.remove("is-dragging");
    try { canvas.releasePointerCapture(e.pointerId); } catch { /* noop */ }
  }
  function onPointerLeave() {
    hoverTargetLon = 0;
    hoverTargetLat = 0;
    if (reduceMotion) renderFrame(performance.now());
  }

  canvas.addEventListener("pointerdown", onPointerDown);
  canvas.addEventListener("pointermove", onPointerMove);
  canvas.addEventListener("pointerup", onPointerUp);
  canvas.addEventListener("pointercancel", onPointerUp);
  canvas.addEventListener("pointerleave", onPointerLeave);

  let nextRouteIndex = 0;
  let lastSpawn = -Infinity;
  const activeArcs = [];

  function spawnArc(now) {
    const route = ARC_ROUTES[nextRouteIndex % ARC_ROUTES.length];
    const label = createLabel(nextRouteIndex);
    nextRouteIndex++;
    activeArcs.push({ route, phase: "drawing", phaseStart: now, ...label });
  }

  function arcPoint(route, t) {
    const v0 = latLonToVec3(route.lat, route.lon);
    const v1 = latLonToVec3(route.to.lat, route.to.lon);
    const dir = slerp(v0, v1, t);
    const lift = 1 + 0.22 * Math.sin(Math.PI * t);
    return [dir[0] * lift, dir[1] * lift, dir[2] * lift];
  }

  function project(vec, lon, lat) {
    const [x, y, z] = rotateVec(vec, lon, lat);
    return { x: cx + x * radius, y: cy - y * radius, z };
  }

  // Sphère sombre + halo doré : donne au globe un vrai volume (silhouette
  // pleine, pas juste un nuage de points épars) et une atmosphère qui
  // fait écho au thème doré du reste de la section.
  function renderFrame(now) {
    if (!reduceMotion) {
      hoverLon += (hoverTargetLon - hoverLon) * 0.08;
      hoverLat += (hoverTargetLat - hoverLat) * 0.08;
    }
    const lon = CENTER_LON + dragLon + hoverLon + (reduceMotion ? 0 : Math.sin(now / 3200) * 14);
    const lat = CENTER_LAT + hoverLat + (reduceMotion ? 0 : Math.sin(now / 2600 + 1) * 5);

    // Pas de remplissage de sphère : le fond blanc de la page reste visible,
    // seuls les points (terres) et les arcs de paiement sont dessinés.
    ctx.clearRect(0, 0, cssWidth, cssHeight);

    for (const p of landPoints) {
      const [rx, ry, rz] = rotateVec(p.vec, lon, lat);
      if (rz <= 0) continue;
      const depth = Math.min(1, rz);
      // Profondeur caméra (depth) pour la taille/l'opacité (effet de
      // perspective) ; produit scalaire avec LIGHT pour la couleur
      // (terminator jour/nuit) — deux informations distinctes, là où
      // l'ancien rendu ne faisait que du fondu par profondeur caméra.
      const light = Math.max(0.12, rx * LIGHT[0] + ry * LIGHT[1] + rz * LIGHT[2]);
      const x = cx + rx * radius;
      const y = cy - ry * radius;
      // Un peu de glace sur les terres de haute latitude (Groenland, nord
      // du Canada/Scandinavie…) au lieu du doré partout.
      const iceFactor = Math.min(1, Math.max(0, (Math.abs(p.lat) - 60) / 25));
      const landColor = mixRgb(colorDeep, colorLight, light);
      const color = iceFactor > 0 ? mixRgb(landColor, [240, 248, 255], iceFactor) : landColor;
      ctx.beginPath();
      ctx.fillStyle = rgba(color, 0.5 + 0.45 * depth);
      ctx.arc(x, y, 1.0 + 1.3 * depth, 0, TAU);
      ctx.fill();
    }

    if (!reduceMotion) {
      if (now - lastSpawn >= SPAWN_MS && activeArcs.length < MAX_CONCURRENT_ARCS) {
        spawnArc(now);
        lastSpawn = now;
      }

      for (let i = activeArcs.length - 1; i >= 0; i--) {
        const arc = activeArcs[i];
        const elapsed = now - arc.phaseStart;
        let progress = 0;
        let arcAlpha = 0;
        let labelVisible = false;
        let rippleT = -1;
        let done = false;

        let labelT = 0;

        if (arc.phase === "drawing") {
          progress = Math.min(1, elapsed / DRAW_MS);
          arcAlpha = 1;
          labelVisible = progress > 0.06;
          labelT = Math.min(progress, 0.985);
          if (elapsed >= DRAW_MS) { arc.phase = "hold"; arc.phaseStart = now; }
        } else if (arc.phase === "hold") {
          progress = 1;
          arcAlpha = 1;
          labelVisible = true;
          labelT = 1;
          rippleT = Math.min(1, elapsed / (HOLD_MS + FADE_MS));
          if (elapsed >= HOLD_MS) { arc.phase = "fading"; arc.phaseStart = now; }
        } else if (arc.phase === "fading") {
          progress = 1;
          arcAlpha = 1 - elapsed / FADE_MS;
          labelVisible = arcAlpha > 0;
          labelT = 1;
          rippleT = Math.min(1, (HOLD_MS + elapsed) / (HOLD_MS + FADE_MS));
          if (elapsed >= FADE_MS) done = true;
        }

        if (progress > 0) {
          ctx.beginPath();
          let started = false;
          const steps = 48;
          const maxStep = Math.round(steps * progress);
          for (let s = 0; s <= maxStep; s++) {
            const t = s / steps;
            const { x, y, z } = project(arcPoint(arc.route, t), lon, lat);
            if (z <= -0.15) { started = false; continue; }
            if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
          }
          ctx.strokeStyle = rgba(colorGold, arcAlpha * 0.85);
          ctx.lineWidth = 2;
          ctx.lineCap = "round";
          ctx.stroke();

          const arrival = project(latLonToVec3(arc.route.to.lat, arc.route.to.lon), lon, lat);
          if (rippleT >= 0 && rippleT <= 1 && arrival.z > 0) {
            ctx.beginPath();
            ctx.strokeStyle = rgba(colorLight, (1 - rippleT) * 0.7);
            ctx.lineWidth = 1.5;
            ctx.arc(arrival.x, arrival.y, 4 + rippleT * 16, 0, TAU);
            ctx.stroke();
          }

          const labelPos = labelT >= 1 ? arrival : project(arcPoint(arc.route, labelT), lon, lat);
          if (labelVisible && labelPos.z > 0) {
            arc.el.style.opacity = String(Math.max(0, Math.min(1, arcAlpha)));
            arc.el.style.transform = `translate3d(${labelPos.x}px, ${labelPos.y}px, 0) translate(-50%, -50%)`;
            arc.amountEl.textContent = arc.route.amount;
          } else {
            arc.el.style.opacity = "0";
          }
        }

        if (done) {
          arc.el.remove();
          activeArcs.splice(i, 1);
        }
      }
    }
  }

  let rafId = null;
  let running = false;

  function loop(now) {
    try {
      renderFrame(now);
    } catch (err) {
      console.error("globe render error", err);
    }
    if (running) rafId = requestAnimationFrame(loop);
  }

  function start() {
    if (running) return;
    running = true;
    lastSpawn = -Infinity;
    rafId = requestAnimationFrame(loop);
  }
  function stop() {
    running = false;
    if (rafId !== null) cancelAnimationFrame(rafId);
    rafId = null;
    for (const arc of activeArcs) arc.el.remove();
    activeArcs.length = 0;
  }

  renderFrame(performance.now());

  const sectionEl = canvas.closest(".globe-section") || canvas;

  // Vérification synchrone au montage : ne pas dépendre uniquement du premier
  // callback (async) d'IntersectionObserver pour démarrer la boucle.
  const initialRect = sectionEl.getBoundingClientRect();
  const initiallyVisible = initialRect.bottom > 0 && initialRect.top < window.innerHeight;
  if (initiallyVisible && !reduceMotion) start();

  const intersectionObserver = new IntersectionObserver((entries) => {
    const visible = entries.some((entry) => entry.isIntersecting);
    if (visible && !reduceMotion) start();
    else stop();
  }, { threshold: 0.1 });
  intersectionObserver.observe(sectionEl);

  return function cleanup() {
    stop();
    resizeObserver.disconnect();
    intersectionObserver.disconnect();
    canvas.removeEventListener("pointerdown", onPointerDown);
    canvas.removeEventListener("pointermove", onPointerMove);
    canvas.removeEventListener("pointerup", onPointerUp);
    canvas.removeEventListener("pointercancel", onPointerUp);
    canvas.removeEventListener("pointerleave", onPointerLeave);
    labelsEl.innerHTML = "";
  };
}
