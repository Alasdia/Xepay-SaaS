// Fond animé de la section "Le monde paie..." — même principe que le fond
// de login.js/signup.js (grille fine + cellules qui flashent au hasard +
// particules reliées par des traits), recoloré en doré (--gold) au lieu
// du cyan, et borné au canvas de cette section plutôt qu'au viewport entier.

const GOLD_RGB = "245,158,11";
const GRID_RGB = "15,17,21"; // --text, très atténué : fond clair ici, pas sombre comme sur login/signup
const GRID_CELL = 60;
const POINT_COUNT = 70;
const LINK_DIST = 100;

export function mountGlobeBg(root) {
  const canvas = root.querySelector("[data-globe-bg-canvas]");
  const section = root.querySelector(".globe-section");
  if (!canvas || !section) return () => {};

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const ctx = canvas.getContext("2d");

  let cw = 0;
  let ch = 0;
  let gridCols = 1;
  let gridRows = 1;
  let flashes = [];

  function rebuildGrid() {
    const cols = Math.round(cw / GRID_CELL);
    const rows = Math.round(ch / GRID_CELL);
    gridCols = Number.isFinite(cols) && cols > 0 ? cols : 1;
    gridRows = Number.isFinite(rows) && rows > 0 ? rows : 1;
    flashes = Array.from({ length: gridCols * gridRows }, () => 0);
  }

  function resize() {
    const rect = canvas.getBoundingClientRect();
    // Math.max(1, NaN) === NaN (Math.max propage NaN au lieu de l'ignorer) :
    // on garde une valeur finie et positive quoi qu'il arrive, plutôt que
    // de se fier à Math.max comme garde-fou.
    const w = Math.round(rect.width);
    const h = Math.round(rect.height);
    cw = Number.isFinite(w) && w > 0 ? w : 1;
    ch = Number.isFinite(h) && h > 0 ? h : 1;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(cw * dpr);
    canvas.height = Math.round(ch * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    rebuildGrid();
    if (reduceMotion) renderStatic();
  }

  const resizeObserver = new ResizeObserver(resize);
  resizeObserver.observe(canvas);
  resize();

  const points = Array.from({ length: POINT_COUNT }, () => ({
    x: Math.random() * cw,
    y: Math.random() * ch,
    vx: (Math.random() - 0.5) * 0.3,
    vy: (Math.random() - 0.5) * 0.3,
    r: Math.random() * 1.3 + 0.35,
    o: Math.random() * 0.45 + 0.3,
  }));

  function drawGrid() {
    const cellW = cw / gridCols;
    const cellH = ch / gridRows;
    ctx.strokeStyle = `rgba(${GRID_RGB},0.09)`;
    ctx.lineWidth = 0.5;
    for (let c = 0; c <= gridCols; c++) {
      ctx.beginPath();
      ctx.moveTo(c * cellW, 0);
      ctx.lineTo(c * cellW, ch);
      ctx.stroke();
    }
    for (let r = 0; r <= gridRows; r++) {
      ctx.beginPath();
      ctx.moveTo(0, r * cellH);
      ctx.lineTo(cw, r * cellH);
      ctx.stroke();
    }
    for (let i = 0; i < flashes.length; i++) {
      flashes[i] = Math.max(0, flashes[i] - 0.016);
      if (flashes[i] > 0) {
        ctx.fillStyle = `rgba(${GOLD_RGB},${flashes[i] * 0.18})`;
        ctx.fillRect((i % gridCols) * cellW, Math.floor(i / gridCols) * cellH, cellW, cellH);
      }
    }
  }

  function drawPoint(p) {
    ctx.beginPath();
    ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(${GOLD_RGB},${p.o})`;
    ctx.fill();
  }

  function renderStatic() {
    ctx.clearRect(0, 0, cw, ch);
    drawGrid();
    points.forEach(drawPoint);
  }

  function renderFrame() {
    ctx.clearRect(0, 0, cw, ch);
    drawGrid();
    points.forEach((p) => {
      p.x += p.vx;
      p.y += p.vy;
      if (p.x < 0) p.x = cw;
      if (p.x > cw) p.x = 0;
      if (p.y < 0) p.y = ch;
      if (p.y > ch) p.y = 0;
      drawPoint(p);
    });
    for (let i = 0; i < points.length; i++) {
      for (let j = i + 1; j < points.length; j++) {
        const dx = points[i].x - points[j].x;
        const dy = points[i].y - points[j].y;
        const d = Math.sqrt(dx * dx + dy * dy);
        if (d < LINK_DIST) {
          ctx.beginPath();
          ctx.moveTo(points[i].x, points[i].y);
          ctx.lineTo(points[j].x, points[j].y);
          ctx.strokeStyle = `rgba(${GOLD_RGB},${(1 - d / LINK_DIST) * 0.4})`;
          ctx.lineWidth = 0.5;
          ctx.stroke();
        }
      }
    }
  }

  let flashTimeoutId = null;
  function scheduleFlash() {
    if (flashes.length) flashes[Math.floor(Math.random() * flashes.length)] = 1;
    flashTimeoutId = setTimeout(scheduleFlash, Math.random() * 700 + 150);
  }

  let rafId = null;
  let running = false;
  function loop() {
    renderFrame();
    if (running) rafId = requestAnimationFrame(loop);
  }
  function start() {
    if (running || reduceMotion) return;
    running = true;
    if (flashTimeoutId === null) scheduleFlash();
    rafId = requestAnimationFrame(loop);
  }
  function stop() {
    running = false;
    if (rafId !== null) cancelAnimationFrame(rafId);
    rafId = null;
  }

  if (reduceMotion) {
    renderStatic();
  } else {
    const initialRect = section.getBoundingClientRect();
    const initiallyVisible = initialRect.bottom > 0 && initialRect.top < window.innerHeight;
    if (initiallyVisible) start();
  }

  const intersectionObserver = new IntersectionObserver((entries) => {
    const visible = entries.some((entry) => entry.isIntersecting);
    if (visible && !reduceMotion) start();
    else stop();
  }, { threshold: 0.1 });
  intersectionObserver.observe(section);

  return function cleanup() {
    stop();
    if (flashTimeoutId !== null) clearTimeout(flashTimeoutId);
    resizeObserver.disconnect();
    intersectionObserver.disconnect();
  };
}
