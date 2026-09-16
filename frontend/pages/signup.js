
const cursor=document.getElementById('cursor'),ring=document.getElementById('cursor-ring');
let mx=0,my=0,rx=0,ry=0;
document.addEventListener('mousemove',e=>{mx=e.clientX;my=e.clientY});
(function anim(){cursor.style.left=mx+'px';cursor.style.top=my+'px';rx+=(mx-rx)*.14;ry+=(my-ry)*.14;ring.style.left=rx+'px';ring.style.top=ry+'px';requestAnimationFrame(anim)})();
document.querySelectorAll('a,button,input,.terms-row,.custom-check,.pw-eye').forEach(el=>{
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
  for(let i=0;i<gf.length;i++){
    gf[i]=Math.max(0,gf[i]-.016);
    if(gf[i]>0){
      ctx.fillStyle=`rgba(168,85,247,${gf[i]*.025})`;
      ctx.fillRect((i%GC)*cw,Math.floor(i/GC)*ch,cw,ch);
    }
  }
  pts.forEach(p=>{
    p.x+=p.vx;p.y+=p.vy;
    if(p.x<0)p.x=cv.width;if(p.x>cv.width)p.x=0;
    if(p.y<0)p.y=cv.height;if(p.y>cv.height)p.y=0;
    ctx.beginPath();ctx.arc(p.x,p.y,p.r,0,Math.PI*2);
    ctx.fillStyle=`rgba(168,85,247,${p.o*.6})`;ctx.fill();
  });
  for(let i=0;i<pts.length;i++)for(let j=i+1;j<pts.length;j++){
    const dx=pts[i].x-pts[j].x,dy=pts[i].y-pts[j].y,d=Math.sqrt(dx*dx+dy*dy);
    if(d<100){
      ctx.beginPath();ctx.moveTo(pts[i].x,pts[i].y);ctx.lineTo(pts[j].x,pts[j].y);
      ctx.strokeStyle=`rgba(168,85,247,${(1-d/100)*.07})`;ctx.lineWidth=.4;ctx.stroke();
    }
  }
  requestAnimationFrame(draw);
})();
const ICONS={
  success:`<svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M20 6L9 17l-5-5" stroke="var(--green)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  error:  `<svg width="18" height="18" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="var(--red)" stroke-width="1.6"/><path d="M12 8v4M12 16h.01" stroke="var(--red)" stroke-width="1.8" stroke-linecap="round"/></svg>`,
  warning:`<svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" stroke="var(--gold)" stroke-width="1.6"/><path d="M12 9v4M12 17h.01" stroke="var(--gold)" stroke-width="1.8" stroke-linecap="round"/></svg>`,
  info:   `<svg width="18" height="18" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="var(--violet)" stroke-width="1.6"/><path d="M12 16v-4M12 8h.01" stroke="var(--violet)" stroke-width="1.8" stroke-linecap="round"/></svg>`,
};
const COLORS={success:'var(--green)',error:'var(--red)',warning:'var(--gold)',info:'var(--violet)'};
function showToast(type='info',title='',message='',duration=4000){
  const c=document.getElementById('toast-container');
  const t=document.createElement('div');
  t.className='toast';
  t.style.setProperty('--toast-color',COLORS[type]);
  t.innerHTML=`
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
  c.appendChild(t);
  const bar=t.querySelector('.toast-progress');
  requestAnimationFrame(()=>{bar.style.transition=`width ${duration}ms linear`;bar.style.width='0%'});
  const timer=setTimeout(()=>closeToast(t),duration);
  t._timer=timer;
  return t;
}
function closeToast(t){
  if(!t||!t.parentNode)return;
  clearTimeout(t._timer);t.classList.add('hide');
  setTimeout(()=>t.remove(),380);
}
function togglePw(){
  const inp=document.getElementById('password');
  const open=document.getElementById('eyeOpen'),closed=document.getElementById('eyeClosed');
  if(inp.type==='password'){inp.type='text';open.style.display='none';closed.style.display='block'}
  else{inp.type='password';open.style.display='block';closed.style.display='none'}
}
function checkStrength(val){
  const el=document.getElementById('pwStrength');
  const label=document.getElementById('strengthLabel');
  const bars=[document.getElementById('sb1'),document.getElementById('sb2'),document.getElementById('sb3'),document.getElementById('sb4')];
  if(!val){el.classList.remove('visible');return}
  el.classList.add('visible');
  let score=0;
  if(val.length>=8)score++;
  if(/[A-Z]/.test(val))score++;
  if(/[0-9]/.test(val))score++;
  if(/[^A-Za-z0-9]/.test(val))score++;
  const configs=[
    {cls:'s1',label:'FAIBLE',color:'var(--red)'},
    {cls:'s2',label:'MOYEN',color:'var(--gold)'},
    {cls:'s3',label:'BON',color:'var(--cyan)'},
    {cls:'s4',label:'FORT',color:'var(--green)'},
  ];
  bars.forEach((b,i)=>{
    b.className='sbar';
    if(i<score)b.classList.add(configs[score-1].cls);
  });
  label.textContent=configs[score-1].label;
  label.style.color=configs[score-1].color;
}
let termsAccepted=false;
function toggleTerms(){
  termsAccepted=!termsAccepted;
  const check=document.getElementById('termsCheck');
  if(termsAccepted)check.classList.add('checked');
  else check.classList.remove('checked');
}
async function signup(){
  const btn=document.getElementById('btnSignup');
  const email=document.getElementById('email').value.trim();
  const password=document.getElementById('password').value;

  if(!email||!password){
    showToast('warning','CHAMPS MANQUANTS','Veuillez remplir votre email et votre mot de passe.');
    return;
  }
  if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)){
    showToast('error','EMAIL INVALIDE','Le format de l\'adresse email n\'est pas valide.');
    return;
  }
  if(password.length<8){
    showToast('warning','MOT DE PASSE TROP COURT','Le mot de passe doit contenir au moins 8 caractères.');
    return;
  }
  if(!termsAccepted){
    showToast('info','CONDITIONS REQUISES','Veuillez accepter les conditions d\'utilisation pour continuer.');
    return;
  }
  btn.innerHTML='<span class="spin"></span>Création en cours...';
  btn.disabled=true;
  try{
    const response=await fetch('https://api.alasdia.com/signup',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({email,password})
    });
    let data=null;
    try{data=await response.json()}catch(e){console.error('JSON error',e)}
    if(!data){
      showToast('error','ERREUR SERVEUR','Réponse vide du serveur. Réessayez.');
      btn.innerHTML='Créer mon compte →';btn.disabled=false;return;
    }
    if(data.success){
      btn.classList.add('success');
      btn.innerHTML=`
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" style="vertical-align:middle;margin-right:6px"><path d="M20 6L9 17l-5-5" stroke="#000" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
        Compte créé — Redirection...
      `;
      showToast('success','COMPTE CRÉÉ','Bienvenue sur Xepay ! Redirection vers la connexion...',3500);
      setTimeout(()=>{window.location.href='login.html'},1400);
    }else{
      showToast('error','ERREUR INSCRIPTION',data.message||'Une erreur est survenue. Réessayez.');
      btn.innerHTML='Créer mon compte →';btn.disabled=false;
    }
  }catch(err){
    console.error(err);
    showToast('error','ERREUR SERVEUR','Impossible de joindre le serveur. Réessayez dans quelques instants.');
    btn.innerHTML='Créer mon compte →';btn.disabled=false;
  }
}
document.addEventListener('keydown',e=>{if(e.key==='Enter')signup()});
function loginWithGoogle(){
  const btn=document.getElementById('btnGoogle');
  btn.classList.add('loading');
  btn.innerHTML='<span class="spin" style="border-color:rgba(255,255,255,.15);border-top-color:rgba(255,255,255,.7)"></span>Redirection Google...';
  showToast('info','GOOGLE AUTH','Redirection vers Google en cours...',3000);
  const clientId='366389455040-q0iie187c1ok621vbcl3vkuflib3fvgf.apps.googleusercontent.com';
  const redirectUri='https://api.alasdia.com/auth/google/callback';
  const url=`https://accounts.google.com/o/oauth2/v2/auth?client_id=${clientId}&redirect_uri=${redirectUri}&response_type=code&scope=openid%20email%20profile`;
  setTimeout(()=>{window.location.href=url},800);
}
const hamburger = document.querySelector('.nav-hamburger');
const navLinks = document.querySelector('.nav-links');
hamburger.addEventListener('click', () => {
  navLinks.classList.toggle('open');
  hamburger.classList.toggle('open');
});