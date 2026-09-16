const cursor=document.getElementById('cursor'),ring=document.getElementById('cursor-ring');
let mx=0,my=0,rx=0,ry=0;
document.addEventListener('mousemove',e=>{mx=e.clientX;my=e.clientY});
(function anim(){cursor.style.left=mx+'px';cursor.style.top=my+'px';rx+=(mx-rx)*.14;ry+=(my-ry)*.14;ring.style.left=rx+'px';ring.style.top=ry+'px';requestAnimationFrame(anim)})();
document.querySelectorAll('a,button,input').forEach(el=>{
  el.addEventListener('mouseenter',()=>{cursor.style.width='18px';cursor.style.height='18px';ring.style.width='48px';ring.style.height='48px'});
  el.addEventListener('mouseleave',()=>{cursor.style.width='9px';cursor.style.height='9px';ring.style.width='32px';ring.style.height='32px'});
});
const cv=document.getElementById('bg-canvas'),ctx=cv.getContext('2d');
function resize(){cv.width=window.innerWidth;cv.height=window.innerHeight}
resize();window.addEventListener('resize',resize);
const pts=Array.from({length:55},()=>({x:Math.random()*cv.width,y:Math.random()*cv.height,vx:(Math.random()-.5)*.3,vy:(Math.random()-.5)*.3,r:Math.random()*1.3+.35,o:Math.random()*.26+.07}));
const GC=22,GR=13;let gf=Array.from({length:GC*GR},()=>0);
(function tf(){gf[Math.floor(Math.random()*gf.length)]=1;setTimeout(tf,Math.random()*700+150)})();
(function draw(){
  ctx.clearRect(0,0,cv.width,cv.height);
  const cw=cv.width/GC,ch=cv.height/GR;
  ctx.strokeStyle='rgba(255,255,255,.016)';ctx.lineWidth=.5;
  for(let c=0;c<=GC;c++){ctx.beginPath();ctx.moveTo(c*cw,0);ctx.lineTo(c*cw,cv.height);ctx.stroke()}
  for(let r=0;r<=GR;r++){ctx.beginPath();ctx.moveTo(0,r*ch);ctx.lineTo(cv.width,r*ch);ctx.stroke()}
  for(let i=0;i<gf.length;i++){gf[i]=Math.max(0,gf[i]-.016);if(gf[i]>0){ctx.fillStyle=`rgba(0,229,255,${gf[i]*.028})`;ctx.fillRect((i%GC)*cw,Math.floor(i/GC)*ch,cw,ch)}}
  pts.forEach(p=>{
    p.x+=p.vx;p.y+=p.vy;
    if(p.x<0)p.x=cv.width;if(p.x>cv.width)p.x=0;
    if(p.y<0)p.y=cv.height;if(p.y>cv.height)p.y=0;
    ctx.beginPath();ctx.arc(p.x,p.y,p.r,0,Math.PI*2);ctx.fillStyle=`rgba(0,229,255,${p.o})`;ctx.fill();
  });
  for(let i=0;i<pts.length;i++)for(let j=i+1;j<pts.length;j++){
    const dx=pts[i].x-pts[j].x,dy=pts[i].y-pts[j].y,d=Math.sqrt(dx*dx+dy*dy);
    if(d<100){ctx.beginPath();ctx.moveTo(pts[i].x,pts[i].y);ctx.lineTo(pts[j].x,pts[j].y);ctx.strokeStyle=`rgba(0,229,255,${(1-d/100)*.075})`;ctx.lineWidth=.4;ctx.stroke()}
  }
  requestAnimationFrame(draw);
})();
const ICONS = {
  success: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M20 6L9 17l-5-5" stroke="var(--green)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  error:   `<svg width="18" height="18" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="var(--red)" stroke-width="1.6"/><path d="M12 8v4M12 16h.01" stroke="var(--red)" stroke-width="1.8" stroke-linecap="round"/></svg>`,
  warning: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" stroke="var(--gold)" stroke-width="1.6"/><path d="M12 9v4M12 17h.01" stroke="var(--gold)" stroke-width="1.8" stroke-linecap="round"/></svg>`,
  info:    `<svg width="18" height="18" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="var(--cyan)" stroke-width="1.6"/><path d="M12 16v-4M12 8h.01" stroke="var(--cyan)" stroke-width="1.8" stroke-linecap="round"/></svg>`,
};
const COLORS = { success:'var(--green)', error:'var(--red)', warning:'var(--gold)', info:'var(--cyan)' };
function showToast(type='info', title='', message='', duration=4000) {
  const container = document.getElementById('toast-container');
  const t = document.createElement('div');
  t.className = 'toast';
  t.style.setProperty('--toast-color', COLORS[type]);
  t.innerHTML = `
    <div class="toast-icon-wrap">${ICONS[type]}</div>
    <div class="toast-body">
      <div class="toast-title">${title}</div>
      <div class="toast-msg">${message}</div>
    </div>
    <div class="toast-close" onclick="closeToast(this.closest('.toast'))">
      <svg width="10" height="10" viewBox="0 0 12 12" fill="none"><path d="M1 1l10 10M11 1L1 11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
    </div>
    <div class="toast-progress" style="width:100%"></div>
  `;
  container.appendChild(t);
  const bar = t.querySelector('.toast-progress');
  requestAnimationFrame(() => {
    bar.style.transition = `width ${duration}ms linear`;
    bar.style.width = '0%';
  });
  const timer = setTimeout(() => closeToast(t), duration);
  t._timer = timer;
  return t;
}
function closeToast(t) {
  if (!t || !t.parentNode) return;
  clearTimeout(t._timer);
  t.classList.add('hide');
  setTimeout(() => t.remove(), 380);
}
function togglePw() {
  const inp = document.getElementById('password');
  const open = document.getElementById('eyeOpen');
  const closed = document.getElementById('eyeClosed');
  if (inp.type === 'password') {
    inp.type = 'text';
    open.style.display = 'none';
    closed.style.display = 'block';
  } else {
    inp.type = 'password';
    open.style.display = 'block';
    closed.style.display = 'none';
  }
}
let awaitingTwoFa = false;
let twoFaEmail = '';
let twoFaWorkspaceId = '';

function handleSubmit() {
  if (awaitingTwoFa) {
    verifyTwoFaCode();
  } else {
    login();
  }
}
function toggleForgotPassword(e) {
  e.preventDefault();
  const fields = document.getElementById('forgot-fields');
  fields.style.display = fields.style.display === 'none' ? 'block' : 'none';
}
async function submitForgotPassword() {
  const email = document.getElementById('email').value.trim();
  const code = document.getElementById('forgot-code').value.trim();
  const new_password = document.getElementById('forgot-new-pwd').value;
  const confirm_password = document.getElementById('forgot-confirm-pwd').value;

  if (!email || !code || !new_password || !confirm_password) {
    showToast('warning', 'CHAMPS MANQUANTS', 'Veuillez remplir tous les champs.');
    return;
  }
  if (code.length !== 6) {
    showToast('warning', 'CODE INVALIDE', 'Le code Authenticator doit faire 6 chiffres.');
    return;
  }
  if (new_password !== confirm_password) {
    showToast('error', 'ERREUR', 'Les mots de passe ne correspondent pas.');
    return;
  }
  const btn = document.getElementById('btnResetPwd');
  btn.innerHTML = '<span class="spin"></span>Réinitialisation...';
  btn.disabled = true;
  try {
    const res = await fetch('https://api.alasdia.com/reset-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: email,
        code: code,
        new_password: new_password,
        confirm_password: confirm_password
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Erreur lors de la réinitialisation');
    showToast('success', 'SUCCÈS', 'Mot de passe mis à jour avec succès.');
    document.getElementById('forgot-fields').style.display = 'none';
  } catch (err) {
    showToast('error', 'ERREUR', err.message);
  } finally {
    btn.innerHTML = 'Réinitialiser le mot de passe →';
    btn.disabled = false;
  }
}
async function login() {
  const btn = document.getElementById('btnLogin');
  const email = document.getElementById('email').value.trim();
  const password = document.getElementById('password').value;

  if (!email || !password) {
    showToast('warning', 'CHAMPS MANQUANTS', 'Veuillez remplir votre email et votre mot de passe.');
    return;
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    showToast('error', 'EMAIL INVALIDE', 'Le format de l\'adresse email n\'est pas valide.');
    return;
  }
  btn.innerHTML = '<span class="spin"></span>Connexion en cours...';
  btn.disabled = true;
  try {
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);
    const response = await fetch('https://api.alasdia.com/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData
    });
    const data = await response.json();
    console.log(data);
    if (data.requires_2fa) {
      awaitingTwoFa = true;
      twoFaEmail = data.email;
      twoFaWorkspaceId = data.workspace_id;
      document.getElementById('twofa-field').style.display = 'block';
      document.getElementById('email').disabled = true;
      document.getElementById('password').disabled = true;
      btn.innerHTML = 'Vérifier →';
      btn.disabled = false;
      showToast('info', 'VÉRIFICATION REQUISE', 'Entrez le code de votre application d\'authentification.', 4000);
      setTimeout(() => document.getElementById('twofa-code').focus(), 100);
      return;
    }
    if (data.access_token && data.account_id) {
      finalizeLogin(data.access_token, email, data.workspace_id, data.account_id);
    } else {
      showToast('error', 'ACCÈS REFUSÉ', 'Email ou mot de passe incorrect. Vérifiez vos identifiants.');
      btn.innerHTML = 'Se connecter →';
      btn.disabled = false;
    }
  } catch (err) {
    showToast('error', 'ERREUR SERVEUR', 'Impossible de joindre le serveur. Réessayez dans quelques instants.');
    btn.innerHTML = 'Se connecter →';
    btn.disabled = false;
  }
}
async function verifyTwoFaCode() {
  const btn = document.getElementById('btnLogin');
  const code = document.getElementById('twofa-code').value.trim();
  if (!code || code.length !== 6) {
    showToast('warning', 'CODE INVALIDE', 'Entrez un code à 6 chiffres.');
    return;
  }
  btn.innerHTML = '<span class="spin"></span>Vérification...';
  btn.disabled = true;
  try {
    const response = await fetch('https://api.alasdia.com/auth/2fa/verify-login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: twoFaEmail, code })
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || 'Code incorrect');
    }
    finalizeLogin(data.access_token, twoFaEmail, data.workspace_id, null);
  } catch (error) {
    showToast('error', 'CODE INCORRECT', error.message);
    btn.innerHTML = 'Vérifier →';
    btn.disabled = false;
    document.getElementById('twofa-code').value = '';
    document.getElementById('twofa-code').focus();
  }
}
function finalizeLogin(token, email, workspaceId, accountId) {
  const btn = document.getElementById('btnLogin');
  localStorage.setItem('token', token);
  localStorage.setItem('email', email);
  localStorage.setItem('workspace_id', workspaceId);
  btn.classList.add('success');
  btn.innerHTML = `
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" style="vertical-align:middle;margin-right:6px"><path d="M20 6L9 17l-5-5" stroke="#000" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
    Connecté — Redirection...
  `;
  showToast('success', 'CONNEXION RÉUSSIE', 'Bienvenue sur votre dashboard Xepay.', 3000);
  setTimeout(() => {
    window.location.href = accountId
      ? `dashboard.html?account_id=${accountId}`
      : `dashboard.html`;
  }, 1200);
}
document.addEventListener('keydown', e => { if (e.key === 'Enter') handleSubmit(); });
function loginWithGoogle() {
  const btn = document.getElementById('btnGoogle');
  btn.classList.add('loading');
  btn.innerHTML = '<span class="spin" style="border-color:rgba(255,255,255,.15);border-top-color:rgba(255,255,255,.7)"></span>Redirection Google...';
  showToast('info', 'GOOGLE AUTH', 'Redirection vers Google en cours...', 3000);
  const clientId = '366389455040-q0iie187c1ok621vbcl3vkuflib3fvgf.apps.googleusercontent.com';
  const redirectUri = 'https://api.alasdia.com/auth/google/callback';
  const url =
  `https://accounts.google.com/o/oauth2/v2/auth?` +
  `client_id=${clientId}` +
  `&redirect_uri=${encodeURIComponent(redirectUri)}` +
  `&response_type=code` +
  `&scope=openid%20email%20profile` +
  `&prompt=select_account` +
  `&access_type=offline` +
  `&include_granted_scopes=true`;
  setTimeout(() => { window.location.href = url; }, 800);
}
window.addEventListener('DOMContentLoaded', () => {
  const params = new URLSearchParams(window.location.search);
  if (params.get('requires_2fa') === 'true') {
    awaitingTwoFa = true;
    twoFaEmail = params.get('email');
    twoFaWorkspaceId = params.get('workspace_id');
    document.getElementById('twofa-field').style.display = 'block';
    document.getElementById('email').value = twoFaEmail;
    document.getElementById('email').disabled = true;
    document.getElementById('password').disabled = true;
    document.querySelector('.btn-google').style.display = 'none';
    document.getElementById('btnLogin').innerHTML = 'Vérifier →';
    showToast('info', 'VÉRIFICATION REQUISE', 'Entrez le code de votre application d\'authentification.', 4000);
    setTimeout(() => document.getElementById('twofa-code').focus(), 100);
  }
});
window.addEventListener('load', () => {
  if (new URLSearchParams(window.location.search).get('requires_2fa') === 'true') return;
  setTimeout(() => {
    showToast('info', 'XEPAY', 'Connectez-vous pour accéder à votre dashboard.', 5000);
  }, 800);
});
