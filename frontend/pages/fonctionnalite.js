const cursor=document.getElementById('cursor'),ring=document.getElementById('cursor-ring');
let mx=0,my=0,rx=0,ry=0;
document.addEventListener('mousemove',e=>{mx=e.clientX;my=e.clientY});
(function anim(){cursor.style.left=mx+'px';cursor.style.top=my+'px';rx+=(mx-rx)*.14;ry+=(my-ry)*.14;ring.style.left=rx+'px';ring.style.top=ry+'px';requestAnimationFrame(anim)})();
document.querySelectorAll('a,button').forEach(el=>{
  el.addEventListener('mouseenter',()=>{cursor.style.width='18px';cursor.style.height='18px';ring.style.width='50px';ring.style.height='50px'});
  el.addEventListener('mouseleave',()=>{cursor.style.width='10px';cursor.style.height='10px';ring.style.width='36px';ring.style.height='36px'});
});
const cv=document.getElementById('bg-canvas'),ctx=cv.getContext('2d');
function resize(){cv.width=window.innerWidth;cv.height=window.innerHeight}
resize();window.addEventListener('resize',resize);
const pts=Array.from({length:50},()=>({x:Math.random()*cv.width,y:Math.random()*cv.height,vx:(Math.random()-.5)*.35,vy:(Math.random()-.5)*.35,r:Math.random()*1.4+.4,o:Math.random()*.3+.08}));
const GC=22,GR=13;let gf=Array.from({length:GC*GR},()=>0);
function tf(){gf[Math.floor(Math.random()*gf.length)]=1;setTimeout(tf,Math.random()*700+150)}tf();
(function draw(){
  ctx.clearRect(0,0,cv.width,cv.height);
  const cw=cv.width/GC,ch=cv.height/GR;
  ctx.strokeStyle='rgba(255,255,255,.02)';ctx.lineWidth=.5;
  for(let c=0;c<=GC;c++){ctx.beginPath();ctx.moveTo(c*cw,0);ctx.lineTo(c*cw,cv.height);ctx.stroke()}
  for(let r=0;r<=GR;r++){ctx.beginPath();ctx.moveTo(0,r*ch);ctx.lineTo(cv.width,r*ch);ctx.stroke()}
  for(let i=0;i<gf.length;i++){gf[i]=Math.max(0,gf[i]-.018);if(gf[i]>0){ctx.fillStyle=`rgba(0,229,255,${gf[i]*.032})`;ctx.fillRect((i%GC)*cw,Math.floor(i/GC)*ch,cw,ch)}}
  pts.forEach(p=>{
    p.x+=p.vx;p.y+=p.vy;
    if(p.x<0)p.x=cv.width;if(p.x>cv.width)p.x=0;if(p.y<0)p.y=cv.height;if(p.y>cv.height)p.y=0;
    ctx.beginPath();ctx.arc(p.x,p.y,p.r,0,Math.PI*2);ctx.fillStyle=`rgba(0,229,255,${p.o})`;ctx.fill();
  });
  for(let i=0;i<pts.length;i++)for(let j=i+1;j<pts.length;j++){
    const dx=pts[i].x-pts[j].x,dy=pts[i].y-pts[j].y,d=Math.sqrt(dx*dx+dy*dy);
    if(d<110){ctx.beginPath();ctx.moveTo(pts[i].x,pts[i].y);ctx.lineTo(pts[j].x,pts[j].y);ctx.strokeStyle=`rgba(0,229,255,${(1-d/110)*.09})`;ctx.lineWidth=.4;ctx.stroke()}
  }
  requestAnimationFrame(draw);
})();
document.querySelectorAll('.feat-tab').forEach(t=>{
  t.addEventListener('click',()=>{document.querySelectorAll('.feat-tab').forEach(x=>x.classList.remove('active'));t.classList.add('active')});
});
const io=new IntersectionObserver(entries=>{
  entries.forEach(e=>{if(e.isIntersecting){e.target.classList.add('visible');io.unobserve(e.target)}});
},{threshold:.1});
document.querySelectorAll('.reveal,.feat-card').forEach(el=>io.observe(el));
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
