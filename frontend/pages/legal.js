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
const PARTICLES = 36;
const particles = Array.from({length: PARTICLES}, () => ({
  x: Math.random() * canvas.width,
  y: Math.random() * canvas.height,
  vx: (Math.random() - 0.5) * 0.25,
  vy: (Math.random() - 0.5) * 0.25,
  r: Math.random() * 1.3 + 0.4,
  opacity: Math.random() * 0.3 + 0.08,
}));
function drawBg() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  particles.forEach(p => {
    p.x += p.vx; p.y += p.vy;
    if (p.x < 0) p.x = canvas.width; if (p.x > canvas.width) p.x = 0;
    if (p.y < 0) p.y = canvas.height; if (p.y > canvas.height) p.y = 0;
    ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(0,229,255,${p.opacity})`;
    ctx.fill();
  });
  requestAnimationFrame(drawBg);
}
drawBg();

const hamburger = document.querySelector('.nav-hamburger');
const navLinks = document.querySelector('.nav-links');
if (hamburger && navLinks) {
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
}

// Sommaire : défilement doux + surbrillance de la section active.
const tocLinks = document.querySelectorAll('.legal-toc a');
const sections = Array.from(tocLinks).map(a => document.querySelector(a.getAttribute('href')));
tocLinks.forEach(a => {
  a.addEventListener('click', e => {
    e.preventDefault();
    const target = document.querySelector(a.getAttribute('href'));
    if (target) target.scrollIntoView({ behavior: 'smooth' });
  });
});
const tocObserver = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    const link = document.querySelector(`.legal-toc a[href="#${entry.target.id}"]`);
    if (!link) return;
    if (entry.isIntersecting) {
      tocLinks.forEach(a => a.classList.remove('active'));
      link.classList.add('active');
    }
  });
}, { rootMargin: '-110px 0px -70% 0px' });
sections.forEach(s => { if (s) tocObserver.observe(s); });
