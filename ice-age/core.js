const clamp=(x,a=0,b=1)=>Math.min(b,Math.max(a,x));
const lerp=(a,b,t)=>a+(b-a)*t;
const ease=t=>{t=clamp(t);return t<.5?2*t*t:1-Math.pow(-2*t+2,2)/2};
const seg=(t,a,b)=>ease((t-a)/(b-a));          // eased 0..1 between times
const lin=(t,a,b)=>clamp((t-a)/(b-a));
const GY=600;                                   // ground baseline (feet)
const INK='#161616'; let FS=2.0;

// ---------- figure system (2-bone IK) ----------
function ik(ax,ay,bx,by,l1,l2,dir=1){
  let dx=bx-ax,dy=by-ay,d=Math.hypot(dx,dy);
  const m=l1+l2-0.01; if(d>m){dx*=m/d;dy*=m/d;d=m;bx=ax+dx;by=ay+dy}
  if(d<1e-3)d=1e-3;
  const a=(l1*l1-l2*l2+d*d)/(2*d), h=Math.sqrt(Math.max(0,l1*l1-a*a));
  const mx=ax+dx*a/d,my=ay+dy*a/d;
  return [mx+dir*h*dy/d, my-dir*h*dx/d, bx,by];
}
function line(pts,w=5){c.strokeStyle=INK;c.lineWidth=w;c.lineCap='round';c.lineJoin='round';c.beginPath();c.moveTo(pts[0],pts[1]);for(let i=2;i<pts.length;i+=2)c.lineTo(pts[i],pts[i+1]);c.stroke()}
function dot(x,y,r,col=INK){c.fillStyle=col;c.beginPath();c.arc(x,y,r,0,7);c.fill()}

/* f: x, s(scale), flip(1/-1 facing right/left), hipY, feet[[x,y],[x,y]], hands[[x,y],[x,y]] (local, from origin),
   face{m:'smile|sad|o|flat|worry|grin', up:0..1, blink}, hair, hood, coat, coatCol, hs(head scale), tilt, lean */
function figure(f){
  const s=f.s||1, fl=f.flip||1, hs=f.hs||1, hipY=f.hipY??-66, lean=f.lean||0;
  c.save(); c.translate(f.x,f.y??GY); c.scale(s*fl*FS,s*FS);
  const sh=[lean,hipY-48], hip=[0,hipY];
  const hr=22*hs, hc=[lean*1.4+(f.tilt||0)*10, hipY-48-hr-4];
  // legs
  const feet=f.feet||[[-12,0],[12,0]];
  for(const ft of feet){ const k=ik(hip[0],hip[1],ft[0],ft[1],34,34,1); line([hip[0],hip[1],k[0],k[1],k[2],k[3]]); // foot
    c.strokeStyle=INK;c.lineWidth=5;c.lineCap='round';c.beginPath();c.moveTo(k[2],k[3]);c.lineTo(k[2]+9,k[3]);c.stroke(); }
  // torso
  line([hip[0],hip[1],sh[0],sh[1]]);
  // coat (behind arms)
  if(f.coat){ const cl=f.coatLen||0.85, bot=sh[1]+(hip[1]+34-sh[1])*cl*1.25;
    c.fillStyle=f.coatCol||'#7a6a58'; c.beginPath();
    c.moveTo(sh[0]-16,sh[1]-2); c.lineTo(sh[0]+16,sh[1]-2);
    const n=7; for(let i=0;i<=n;i++){const x=lerp(26,-26,i/n)+lean*.3,y=bot+(i%2?9:-3);c.lineTo(x,y)}
    c.closePath(); c.fill();
    c.strokeStyle='rgba(0,0,0,.25)';c.lineWidth=2;for(let i=0;i<6;i++){c.beginPath();c.moveTo(-18+i*7,sh[1]+10);c.lineTo(-20+i*7+lean*.2,bot-6);c.stroke()}
  }
  // arms
  const hands=f.hands||[[-22,-hipY*0+ -10+ (hipY+30)],[22,hipY+30]];
  hands.forEach((h,i)=>{ const hx=h[0],hy=h[1]; const k=ik(sh[0],sh[1],hx,hy,30,30,i?-1:1); line([sh[0],sh[1],k[0],k[1],k[2],k[3]]); });
  // head
  c.save(); c.translate(hc[0],hc[1]); c.rotate((f.tilt||0)*0.35);
  if(f.hair==='long'||f.hair==='pony'){ c.fillStyle=f.hairCol||'#4a3426'; c.beginPath();c.ellipse(-6*1,hr*.15,hr*1.05,hr*1.25,0,0,7);c.fill(); if(f.hair==='pony'){c.beginPath();c.ellipse(-hr*1.05,hr*.9,hr*.4,hr*1.1,.3,0,7);c.fill()}}
  c.fillStyle='#fff';c.strokeStyle=INK;c.lineWidth=4;c.beginPath();c.arc(0,0,hr,0,7);c.fill();c.stroke();
  if(f.hair==='spiky'||f.hair==='short'){ c.fillStyle=f.hairCol||'#4a3426'; c.beginPath(); const n=9;
    for(let i=0;i<=n;i++){const a=Math.PI*(1.05+0.9*i/n), r=hr*(i%2?1.15:1.4); c.lineTo(Math.cos(a)*r,Math.sin(a)*r)}
    c.lineTo(Math.cos(Math.PI*1.95)*hr*.9,Math.sin(Math.PI*1.95)*hr*.9);
    for(let i=n;i>=0;i--){const a=Math.PI*(1.05+0.9*i/n);c.lineTo(Math.cos(a)*hr*.88,Math.sin(a)*hr*.88)} c.closePath();c.fill();}
  if(f.long2){c.fillStyle=f.hairCol||'#4a3426';c.beginPath();c.arc(0,-hr*.15,hr*1.02,Math.PI*1.05,Math.PI*1.95);c.lineTo(hr*.9,-hr*.4);c.lineTo(-hr*.9,-hr*.4);c.fill()}
  // face
  const fc=f.face||{}, up=fc.up||0, ex=hr*.38, ey=-hr*.08-up*hr*.35, bl=fc.blink?0.15:1;
  c.save();c.scale(1,1);
  dot(-ex*.7+ (fc.lx||0),ey,hr*.1*(fc.blink?.4:1)); dot(ex*.7+(fc.lx||0),ey,hr*.1*(fc.blink?.4:1));
  c.strokeStyle=INK;c.lineWidth=3;c.lineCap='round';
  const my=hr*.45-up*hr*.1, m=fc.m||'flat';
  c.beginPath();
  if(m==='smile'){c.arc(0,my-hr*.2,hr*.35,.2,Math.PI-.2)}
  else if(m==='grin'){c.arc(0,my-hr*.25,hr*.42,.1,Math.PI-.1);c.closePath();c.fillStyle='#fff';c.fill()}
  else if(m==='sad'){c.arc(0,my+hr*.35,hr*.3,Math.PI+.3,-.3)}
  else if(m==='worry'){c.moveTo(-hr*.3,my+hr*.05);c.quadraticCurveTo(0,my-hr*.12,hr*.3,my+hr*.1)}
  else if(m==='o'){c.arc(0,my,hr*.12+ (fc.mo||0)*hr*.1,0,7)}
  else {c.moveTo(-hr*.2,my);c.lineTo(hr*.2,my)}
  c.stroke();
  if(fc.brow){const b=fc.brow;c.beginPath();c.moveTo(-ex*1.2,ey-hr*.3-b*3);c.lineTo(-ex*.2,ey-hr*.3+b*3);c.moveTo(ex*1.2,ey-hr*.3-b*3);c.lineTo(ex*.2,ey-hr*.3+b*3);c.lineWidth=2.5;c.stroke()}
  c.restore();
  c.restore();
  // hood
  if(f.hood){ c.fillStyle=f.hoodCol||'#6d6558'; c.beginPath();
    c.arc(hc[0],hc[1]-2,hr*1.22,Math.PI*0.85,Math.PI*2.15); c.lineTo(hc[0]+hr*1.1,hc[1]+hr*.95); c.lineTo(hc[0]-hr*1.1,hc[1]+hr*.95); c.closePath();
    // cut face opening
    c.moveTo(hc[0]+hr*.78,hc[1]+hr*.1);c.arc(hc[0],hc[1]+hr*.05,hr*.82,0,Math.PI*2,true);
    c.fill('evenodd'); }
  c.restore();
  return {hx:f.x+fl*s*FS*hc[0],hy:(f.y??GY)+s*FS*hc[1],hr:hr*s*FS};
}
// ---- motion helpers
function walkFeet(p,stride=20,lift=10){return [[Math.sin(p)*stride,-Math.max(0,Math.cos(p))*lift],[-Math.sin(p)*stride,-Math.max(0,-Math.cos(p))*lift]]}
function walkArms(p,hipY=-66,sw=14){return [[-Math.sin(p)*sw,hipY+34],[Math.sin(p)*sw+4,hipY+34]]}

function glowFoot(x,y,a,sc=1){
  c.save();c.translate(x,y);c.scale(sc*1.8,sc*1.0);
  c.shadowColor=`rgba(255,215,90,${a})`;c.shadowBlur=30*a;
  c.fillStyle=`rgba(255,226,120,${.25+.75*a})`;c.strokeStyle=`rgba(190,130,20,${.4+.6*a})`;c.lineWidth=2.5;
  c.beginPath();c.ellipse(0,0,13,26,0,0,7);c.fill();c.stroke();
  for(let i=0;i<4;i++){c.beginPath();c.arc(-9+i*6,-32+Math.abs(i-1.5)*2.5,3.2,0,7);c.fill()}
  c.restore();
}
// ================= v2: doodle-explainer scenes =================
const RED='#d62828', GREEN='#2e9e4f', GOLD='#f4c430', NAVY='#17213f';
const outBack=x=>{x=clamp(x);const s=1.70158;return x<=0?0:1+(s+1)*Math.pow(x-1,3)+s*Math.pow(x-1,2)};
const pop=(u,d=0,dur=.4)=>outBack((u-d)/dur);
function at(x,y,k,fn,rot=0){if(k<=0.001)return;c.save();c.translate(x,y);c.rotate(rot);c.scale(k,k);fn();c.restore()}
function st(w=5,col=INK){c.lineWidth=w;c.strokeStyle=col;c.lineCap='round';c.lineJoin='round'}
function txt(s,x,y,size,col=INK,align='center'){
  const F=z=>`800 ${z}px "Trebuchet MS","DejaVu Sans",Arial,sans-serif`;c.font=F(size);c.textAlign=align;c.fillStyle=col;
  const m=c.getTransform(),k=Math.abs(m.a)||1,M=70,maxPx=CW-2*M;let w=c.measureText(s).width*k;
  if(w>maxPx){size=Math.floor(size*maxPx/w);c.font=F(size);w=c.measureText(s).width*k}
  if(align==='center'){const cx=m.e+x*m.a;if(cx-w/2<M)x+= (M-(cx-w/2))/m.a;if(cx+w/2>CW-M)x-= (cx+w/2-(CW-M))/m.a}
  c.fillText(s,x,y)}
function arrow(x1,y1,x2,y2,k,col=RED,w=22){ if(k<=0)return; const ex=lerp(x1,x2,k),ey=lerp(y1,y2,k),a=Math.atan2(y2-y1,x2-x1);
  c.save();c.translate(ex,ey);c.rotate(a);c.fillStyle=col;st(4);c.beginPath();c.moveTo(0,0);c.lineTo(-w*1.7,-w*1.2);c.lineTo(-w*1.7,w*1.2);c.closePath();c.fill();c.stroke();c.restore();
  c.save();c.strokeStyle=col;c.lineWidth=w;c.lineCap='butt';c.beginPath();c.moveTo(x1,y1);c.lineTo(ex-Math.cos(a)*w*1.5,ey-Math.sin(a)*w*1.5);c.stroke();c.restore()}
function qmark(x,y,s,col=RED){c.save();c.translate(x,y);c.scale(s,s);txt('?',0,0,150,col);c.restore()}
function bubbleCloud(x,y,w,h,tail='l'){c.fillStyle='#fff';st(4);c.beginPath();
  for(let i=0;i<12;i++){const a=i/12*Math.PI*2;c.ellipse(x+Math.cos(a)*w*.82,y+Math.sin(a)*h*.8,w*.28,h*.34,0,0,7)}c.fill();c.stroke();
  c.beginPath();c.ellipse(x,y,w*.85,h*.85,0,0,7);c.fill();
  for(let i=0;i<3;i++){c.beginPath();c.arc(x+(tail==='l'?-1:1)*(w*.7+i*18),y+h*.9+i*20,10-i*2.5,0,7);c.fill();c.stroke()}}
function bread(x,y,s=1,rot=0){at(x,y,s,()=>{c.fillStyle='#e0a95e';st(4);c.beginPath();c.ellipse(0,0,46,26,0,0,7);c.fill();c.stroke();c.strokeStyle='#a9733a';c.lineWidth=3;
  for(const dx of [-18,0,18]){c.beginPath();c.moveTo(dx-6,-12);c.lineTo(dx+4,6);c.stroke()}},rot)}
function bowl(x,y,s=1,food=false){at(x,y,s,()=>{c.fillStyle='#fff';st(5);c.beginPath();c.moveTo(-60,-20);c.quadraticCurveTo(-55,36,0,40);c.quadraticCurveTo(55,36,60,-20);c.closePath();c.fill();c.stroke();
  c.beginPath();c.ellipse(0,-20,60,14,0,0,7);c.fillStyle=food?'#e0a95e':'#e9e9e9';c.fill();c.stroke()})}
function cloud(x,y,s=1){at(x,y,s,()=>{const cs=[[-62,14,34],[-24,-20,42],[28,-14,38],[62,16,30],[0,16,40]];c.fillStyle='#b9c7d6';st(5);
  for(const k of cs){c.beginPath();c.arc(k[0],k[1],k[2],0,7);c.stroke()}
  for(const k of cs){c.beginPath();c.arc(k[0],k[1],k[2],0,7);c.fill()}
  c.beginPath();c.rect(-62,14,124,28);c.fill()})}
function drops(x,y,t,n=6,h=140){c.fillStyle='#4aa3df';st(3);for(let i=0;i<n;i++){const p=((t*1.3+i/n)%1), dx=x+(i-n/2)*20+(i%2)*6, dy=y+p*h;c.globalAlpha=1-p*.5;c.beginPath();c.moveTo(dx,dy-12);c.quadraticCurveTo(dx+9,dy+4,dx,dy+8);c.quadraticCurveTo(dx-9,dy+4,dx,dy-12);c.fill();c.stroke()}c.globalAlpha=1}
function heart(x,y,s,col=RED){at(x,y,s,()=>{c.fillStyle=col;st(4);c.beginPath();c.moveTo(0,18);c.bezierCurveTo(-46,-14,-26,-46,0,-20);c.bezierCurveTo(26,-46,46,-14,0,18);c.fill();c.stroke()})}
function check(x,y,s,col=GREEN){at(x,y,s,()=>{c.strokeStyle=col;c.lineWidth=26;c.lineCap='round';c.lineJoin='round';c.beginPath();c.moveTo(-50,0);c.lineTo(-14,38);c.lineTo(56,-44);c.stroke()})}
function cross(x,y,s,col=RED){at(x,y,s,()=>{c.strokeStyle=col;c.lineWidth=24;c.lineCap='round';c.beginPath();c.moveTo(-40,-40);c.lineTo(40,40);c.moveTo(40,-40);c.lineTo(-40,40);c.stroke()})}
function sparkle(x,y,r,col='#ffe9a0'){c.fillStyle=col;c.beginPath();c.moveTo(x,y-r);c.quadraticCurveTo(x,y,x+r,y);c.quadraticCurveTo(x,y,x,y+r);c.quadraticCurveTo(x,y,x-r,y);c.quadraticCurveTo(x,y,x,y-r);c.fill()}
function houseDoor(x,y,s=1,woman=false,t=0){at(x,y,s,()=>{
  c.fillStyle='#c79a6b';st(6);c.beginPath();c.rect(-210,-330,420,330);c.fill();c.stroke();
  c.fillStyle='#7a4f35';c.beginPath();c.moveTo(-250,-325);c.lineTo(0,-470);c.lineTo(250,-325);c.closePath();c.fill();c.stroke();
  c.fillStyle='#ffd978';c.beginPath();c.rect(-70,-250,140,250);c.fill();c.stroke();   // open door, warm light
  c.fillStyle='#e8d9a8';c.beginPath();c.rect(100,-250,70,70);c.fill();c.stroke();c.beginPath();c.moveTo(135,-250);c.lineTo(135,-180);c.moveTo(100,-215);c.lineTo(170,-215);c.stroke();
  c.fillStyle='#6b4a34';c.beginPath();c.rect(-210,0,420,10);c.fill();})}
function phone(x,y,s,screen,rot=0){at(x,y,s,()=>{c.fillStyle='#222';st(6);c.beginPath();c.roundRect(-70,-130,140,260,22);c.fill();c.stroke();
  c.fillStyle=screen==='job'?'#e4f7e8':'#8fd3ff';c.beginPath();c.roundRect(-58,-112,116,224,10);c.fill();
  if(screen==='job'){check(0,-30,.9);txt('JOB',0,50,28,GREEN);txt('OFFER',0,82,28,GREEN)}
  else {c.fillStyle='#fff';c.beginPath();c.arc(0,-62,26,0,7);c.fill();c.fillStyle='#9aa7b4';c.beginPath();c.arc(0,-68,9,0,7);c.fill();c.beginPath();c.ellipse(0,-46,16,9,0,Math.PI,0);c.fill();txt('CALLING',0,-10,20,'#0b3a5b');c.fillStyle='#e53935';c.beginPath();c.arc(-30,74,20,0,7);c.fill();c.fillStyle='#2e9e4f';c.beginPath();c.arc(30,74,20,0,7);c.fill();st(5,'#fff');c.beginPath();c.moveTo(22,80);c.quadraticCurveTo(24,66,38,66);c.stroke()}},rot)}
function briefcase(x,y,s){at(x,y,s,()=>{c.fillStyle='#8b5a2b';st(6);c.beginPath();c.roundRect(-70,-40,140,100,12);c.fill();c.stroke();c.beginPath();c.roundRect(-26,-70,52,30,8);c.stroke();c.fillStyle=GOLD;c.beginPath();c.rect(-12,-6,24,22);c.fill();c.stroke();c.beginPath();c.moveTo(-70,10);c.lineTo(70,10);c.stroke()})}
function coin(x,y,r){c.fillStyle=GOLD;st(4);c.beginPath();c.ellipse(x,y,r,r*.45,0,0,7);c.fill();c.stroke();c.beginPath();c.ellipse(x,y-8,r,r*.45,0,0,7);c.fill();c.stroke()}
function coinStack(x,y,n,k=1){for(let i=0;i<n;i++){coin(x,y-i*14*k,46*k)}}
function table(x,y,w=360){c.fillStyle='#9b6b43';st(6);c.beginPath();c.rect(x-w/2,y-20,w,28);c.fill();c.stroke();c.beginPath();c.rect(x-w/2+26,y+8,26,150);c.rect(x+w/2-52,y+8,26,150);c.fill();c.stroke()}
function tag(x,y,s,text,col='#ffe45e',rot=-.08){at(x,y,s,()=>{c.fillStyle=col;st(5);c.beginPath();c.moveTo(-170,0);c.lineTo(-136,-40);c.lineTo(170,-40);c.lineTo(170,40);c.lineTo(-136,40);c.closePath();c.fill();c.stroke();c.fillStyle='#fff';c.beginPath();c.arc(-130,0,8,0,7);c.fill();c.stroke();txt(text,16,11,32)},rot)}
function rays(cx,cy,t,col='rgba(255,236,150,.55)',n=16,len=900){c.save();c.translate(cx,cy);c.rotate(t*.08);c.fillStyle=col;for(let i=0;i<n;i++){c.rotate(Math.PI*2/n);c.beginPath();c.moveTo(0,0);c.lineTo(len,-34);c.lineTo(len,34);c.closePath();c.fill()}c.restore()}
function glow(x,y,r,col='255,230,120',a=.9){const g=c.createRadialGradient(x,y,0,x,y,r);g.addColorStop(0,`rgba(${col},${a})`);g.addColorStop(1,`rgba(${col},0)`);c.fillStyle=g;c.beginPath();c.arc(x,y,r,0,7);c.fill()}
function motion(x,y,n,len,dir=1){st(5,'#888');for(let i=0;i<n;i++){c.beginPath();c.moveTo(x,y+i*34);c.lineTo(x-dir*len*(1-i*.15),y+i*34);c.stroke()}}
function foot(x,y,sc,a,rot=-.35){ if(a<=0)return; c.save();c.translate(x,y);c.rotate(rot);c.scale(sc*1.9,sc*1.9);
  c.shadowColor=`rgba(255,215,90,${a})`;c.shadowBlur=36*a;c.fillStyle=`rgba(255,226,120,${.25+.75*a})`;c.strokeStyle=`rgba(190,130,20,${.5+.5*a})`;c.lineWidth=2.5;
  c.beginPath();c.moveTo(-10,-14);c.bezierCurveTo(-16,-34,16,-34,14,-10);c.bezierCurveTo(12,10,10,22,4,28);c.bezierCurveTo(-4,34,-12,26,-10,10);c.closePath();c.fill();c.stroke();
  [[-12,-44,5],[-3,-48,4.5],[6,-47,4],[13,-42,3.6],[18,-34,3]].forEach(t=>{c.beginPath();c.arc(t[0],t[1],t[2],0,7);c.fill();c.stroke()});c.restore()}
