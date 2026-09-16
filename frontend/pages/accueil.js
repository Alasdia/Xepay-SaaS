const cursor = document.getElementById('cursor');
const ring   = document.getElementById('cursor-ring');
let mx = 0, my = 0, rx = 0, ry = 0;
document.addEventListener('mousemove', e => { mx = e.clientX; my = e.clientY; });
function animCursor() {
  cursor.style.left = mx + 'px'; cursor.style.top = my + 'px';
  rx += (mx - rx) * 0.15; ry += (my - ry) * 0.15;
  ring.style.left = rx + 'px'; ring.style.top  = ry + 'px';
  requestAnimationFrame(animCursor);
}
animCursor();
document.querySelectorAll('a,button').forEach(el => {
  el.addEventListener('mouseenter', () => {
    cursor.style.width = '20px'; cursor.style.height = '20px';
    ring.style.width = '54px'; ring.style.height = '54px';
    ring.style.borderColor = 'rgba(0,229,255,0.6)';
  });
  el.addEventListener('mouseleave', () => {
    cursor.style.width = '10px'; cursor.style.height = '10px';
    ring.style.width = '36px'; ring.style.height = '36px';
    ring.style.borderColor = 'rgba(0,229,255,0.4)';
  });
});
const canvas = document.getElementById('bg-canvas');
const ctx    = canvas.getContext('2d');
function resizeCanvas() { canvas.width = window.innerWidth; canvas.height = window.innerHeight; }
resizeCanvas();
window.addEventListener('resize', resizeCanvas);
const PARTICLES = 60;
const particles = Array.from({length: PARTICLES}, () => ({
  x: Math.random() * canvas.width,
  y: Math.random() * canvas.height,
  vx: (Math.random() - 0.5) * 0.4,
  vy: (Math.random() - 0.5) * 0.4,
  r: Math.random() * 1.5 + 0.5,
  opacity: Math.random() * 0.4 + 0.1,
}));
const GRID_COLS = 24, GRID_ROWS = 14;
let gridFlash = Array.from({length: GRID_COLS * GRID_ROWS}, () => 0);
function triggerFlash() {
  const i = Math.floor(Math.random() * gridFlash.length);
  gridFlash[i] = 1;
  setTimeout(triggerFlash, Math.random() * 800 + 200);
}
triggerFlash();
function drawBg() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const cw = canvas.width / GRID_COLS, ch = canvas.height / GRID_ROWS;
  for (let i = 0; i < GRID_COLS * GRID_ROWS; i++) {
    const col = i % GRID_COLS, row = Math.floor(i / GRID_COLS);
    gridFlash[i] = Math.max(0, gridFlash[i] - 0.02);
    if (gridFlash[i] > 0) {
      ctx.beginPath();
      ctx.rect(col * cw, row * ch, cw, ch);
      ctx.fillStyle = `rgba(0,229,255,${gridFlash[i] * 0.04})`;
      ctx.fill();
    }
  }
  ctx.strokeStyle = 'rgba(255,255,255,0.025)';
  ctx.lineWidth = 0.5;
  for (let c = 0; c <= GRID_COLS; c++) {
    ctx.beginPath(); ctx.moveTo(c * cw, 0); ctx.lineTo(c * cw, canvas.height); ctx.stroke();
  }
  for (let r = 0; r <= GRID_ROWS; r++) {
    ctx.beginPath(); ctx.moveTo(0, r * ch); ctx.lineTo(canvas.width, r * ch); ctx.stroke();
  }
  particles.forEach(p => {
    p.x += p.vx; p.y += p.vy;
    if (p.x < 0) p.x = canvas.width; if (p.x > canvas.width) p.x = 0;
    if (p.y < 0) p.y = canvas.height; if (p.y > canvas.height) p.y = 0;
    ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(0,229,255,${p.opacity})`;
    ctx.fill();
  });
  for (let i = 0; i < particles.length; i++) {
    for (let j = i + 1; j < particles.length; j++) {
      const dx = particles[i].x - particles[j].x;
      const dy = particles[i].y - particles[j].y;
      const dist = Math.sqrt(dx*dx + dy*dy);
      if (dist < 120) {
        ctx.beginPath();
        ctx.moveTo(particles[i].x, particles[i].y);
        ctx.lineTo(particles[j].x, particles[j].y);
        ctx.strokeStyle = `rgba(0,229,255,${(1 - dist/120) * 0.12})`;
        ctx.lineWidth = 0.5;
        ctx.stroke();
      }
    }
  }
  requestAnimationFrame(drawBg);
}
drawBg();
function animCounter(el) {
  const to = parseInt(el.dataset.to);
  const duration = 1800;
  const start = performance.now();
  function step(now) {
    const t = Math.min((now - start) / duration, 1);
    const ease = 1 - Math.pow(1 - t, 3);
    el.textContent = Math.floor(ease * to);
    if (t < 1) requestAnimationFrame(step);
    else el.textContent = to;
  }
  requestAnimationFrame(step);
}
const io = new IntersectionObserver((entries) => {
  entries.forEach(e => {
    if (e.isIntersecting) {
      e.target.classList.add('visible');
      e.target.querySelectorAll('.counter').forEach(animCounter);
      io.unobserve(e.target);
    }
  });
}, { threshold: 0.12 });
document.querySelectorAll('.reveal').forEach(el => io.observe(el));
const statsBar = document.querySelector('.stats-bar');
if (statsBar) {
  const io2 = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        e.target.querySelectorAll('.counter').forEach(animCounter);
        io2.unobserve(e.target);
      }
    });
  }, { threshold: 0.5 });
  io2.observe(statsBar);
}
const hamburger = document.querySelector('.nav-hamburger');
const navLinks = document.querySelector('.nav-links');
hamburger.addEventListener('click', () => {
  navLinks.classList.toggle('open');
  hamburger.classList.toggle('open');
});
document.querySelectorAll('.nav-links a').forEach(link => {
  link.addEventListener('click', () => {
    navLinks.classList.remove('open');
    hamburger.classList.remove('open');
  });
});
