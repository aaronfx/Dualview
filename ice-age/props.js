// ================= Ice Age props & sets (design space 1280x720, ground y=GY) =================
const ICE='#cfe8f5',ICE2='#9fcbe3',SNOW='#f4f9fd',FUR='#9b7b5a',FUR2='#7a5c3c',BONE='#efe6cf',DARK='#0d1430';
const mix=(a,b,t)=>`rgb(${a.map((v,i)=>Math.round(lerp(v,b[i],t))).join(',')})`;
function skyFill(top,bot){const g=c.createLinearGradient(0,0,0,H);g.addColorStop(0,top);g.addColorStop(1,bot);c.fillStyle=g;c.fillRect(-300,-300,W+600,H+600)}
function snowGround(y=GY-70,col=SNOW){c.fillStyle=col;st(3,'#8fb3c9');c.beginPath();c.moveTo(-300,y+10);
  for(let x=-300;x<=W+300;x+=120)c.lineTo(x,y+(Math.sin(x*.013)*10));c.lineTo(W+300,H+300);c.lineTo(-300,H+300);c.closePath();c.fill();c.stroke()}
function iceMountains(off=0,col='#b6d4e6',base=GY-70){c.fillStyle=col;st(3,'#6f93ad');c.beginPath();c.moveTo(-300,base);
  const pk=[[-120,360],[120,200],[360,330],[600,170],[860,320],[1100,210],[1400,340]];pk.forEach(p=>c.lineTo(p[0]+off,p[1]));c.lineTo(1600,base);c.closePath();c.fill();c.stroke();
  c.fillStyle='#fff';for(const p of pk){c.beginPath();c.moveTo(p[0]+off,p[1]);c.lineTo(p[0]+off-34,p[1]+46);c.lineTo(p[0]+off+34,p[1]+46);c.closePath();c.fill()}}
function glacier(x,y,w,h){c.fillStyle='#bfe0f0';st(4,'#5d8fae');c.beginPath();c.moveTo(x,y);for(let i=0;i<=8;i++)c.lineTo(x+i*w/8,y-h+(i%2?-20:14)+Math.sin(i*2.1)*16);c.lineTo(x+w,y);c.closePath();c.fill();c.stroke();
  c.strokeStyle='rgba(95,150,185,.55)';c.lineWidth=2.5;for(let i=1;i<9;i++){c.beginPath();c.moveTo(x+i*w/9,y);c.lineTo(x+i*w/9+(i%3-1)*30,y-h*(.35+.5*((i*37)%10)/10));c.stroke()}
  c.fillStyle='rgba(255,255,255,.35)';c.beginPath();c.moveTo(x+w*.1,y-h*.8);c.lineTo(x+w*.35,y-h*.95);c.lineTo(x+w*.25,y-h*.3);c.closePath();c.fill()}
function snowfall(t,n=70,a=.9){c.fillStyle=`rgba(255,255,255,${a})`;for(let i=0;i<n;i++){const x=((i*97.3+t*(18+(i%5)*6))%1500)-110,y=((i*53.1+t*(55+(i%7)*9))%860)-70;c.beginPath();c.arc(x,y,2+(i%3),0,7);c.fill()}}
function windLines(t,y0=240,n=7,col='rgba(255,255,255,.8)'){st(4,col);for(let i=0;i<n;i++){const y=y0+i*34,x=((t*520+i*210)%1800)-300;c.beginPath();c.moveTo(x,y);c.bezierCurveTo(x+60,y-18,x+120,y+18,x+190,y);c.stroke()}}
function shadow(x,y,w=56){c.fillStyle='rgba(30,60,90,.18)';c.beginPath();c.ellipse(x,y+6,w,10,0,0,7);c.fill()}
function vignetteDark(a){c.fillStyle=`rgba(8,12,34,${a})`;c.fillRect(-300,-300,W+600,H+600)}
function stars(t,n=60){c.fillStyle='#fff';for(let i=0;i<n;i++){const x=(i*173.7)%W,y=(i*91.3)%(GY-120),r=1+((i*7)%3)*.8*(.7+.3*Math.sin(t*2+i));c.beginPath();c.arc(x,y,r,0,7);c.fill()}}
function moon(x,y,r){glow(x,y,r*3,'255,255,230',.25);c.fillStyle='#fff7d6';st(3,'#d8c98c');c.beginPath();c.arc(x,y,r,0,7);c.fill();c.stroke();c.fillStyle='#e8dcae';c.beginPath();c.arc(x-r*.3,y-r*.2,r*.2,0,7);c.fill()}

// ---- people ----
function you(x,o={}){return figure({x,y:GY,s:1,hair:'short',hairCol:'#3a2a1c',coat:true,coatCol:'#3b82d6',coatLen:.32,face:{m:'worry'},...o})}
function hunter(x,o={}){return figure({x,y:GY,s:1,hood:true,hoodCol:FUR2,coat:true,coatCol:FUR,coatLen:.95,face:{m:'smile'},...o})}
function mama(x,o={}){return figure({x,y:GY,s:.95,hair:'pony',hairCol:'#3a2a1c',coat:true,coatCol:'#a98563',coatLen:.95,face:{m:'smile'},...o})}
function kid(x,o={}){return figure({x,y:GY,s:.66,hs:1.45,hair:'spiky',hairCol:'#3a2a1c',coat:true,coatCol:'#8a6a48',coatLen:.7,face:{m:'grin'},...o})}
function elder(x,o={}){return figure({x,y:GY,s:.92,hair:'long',hairCol:'#cfcfcf',coat:true,coatCol:'#7d6a58',coatLen:1,face:{m:'smile'},...o})}
const sitP=fx=>({hipY:-18,feet:[[fx,0],[fx+24,-2]]});
const shiver=(t,a=3)=>Math.sin(t*38)*a;

// ---- animals ----
function mammoth(x,y,s=1,flip=1,t=0,col='#6b4a35'){c.save();c.translate(x,y);c.scale(s*flip,s);
  const bob=Math.sin(t*3)*3;c.fillStyle=col;st(5);
  c.beginPath();c.ellipse(0,-150+bob,170,110,0,0,7);c.fill();c.stroke();                       // body
  c.beginPath();c.ellipse(-120,-190+bob,95,95,0,0,7);c.fill();c.stroke();                     // head/hump
  c.beginPath();c.ellipse(120,-110,90,70,0,0,7);c.fill();c.stroke();
  for(const lx of [-100,-40,60,120]){c.beginPath();c.roundRect(lx-22,-90,44,92,12);c.fill();c.stroke()}
  c.strokeStyle='rgba(30,15,5,.5)';c.lineWidth=3;for(let i=0;i<12;i++){c.beginPath();c.moveTo(-120+i*24,-60);c.lineTo(-126+i*24,-20+(i%3)*8);c.stroke()}
  st(5);c.beginPath();c.moveTo(-182,-160+bob);c.quadraticCurveTo(-230,-100,-212,-20);c.quadraticCurveTo(-208,-4,-196,-14);c.stroke();   // trunk
  c.lineWidth=12;c.strokeStyle='#f1ead2';c.beginPath();c.moveTo(-178,-170+bob);c.quadraticCurveTo(-250,-150,-266,-70);c.quadraticCurveTo(-266,-56,-252,-62);c.stroke();
  c.lineWidth=3;c.strokeStyle=INK;c.beginPath();c.moveTo(-178,-170+bob);c.quadraticCurveTo(-250,-150,-266,-70);c.stroke();
  dot(-150,-205+bob,6);c.restore()}
function eyesDark(x,y,s=1,col='#ffe14d'){c.save();c.translate(x,y);c.scale(s,s);glow(0,0,60,'255,225,70',.35);c.fillStyle=col;c.beginPath();c.ellipse(-16,0,9,6,.2,0,7);c.ellipse(16,0,9,6,-.2,0,7);c.fill();c.fillStyle='#111';c.beginPath();c.ellipse(-16,0,3,5,0,0,7);c.ellipse(16,0,3,5,0,0,7);c.fill();c.restore()}
function wolf(x,y,s=1,flip=1,col='#7b8794'){c.save();c.translate(x,y);c.scale(s*flip,s);c.fillStyle=col;st(4);
  c.beginPath();c.ellipse(0,-50,62,30,0,0,7);c.fill();c.stroke();c.beginPath();c.ellipse(-58,-68,26,22,0,0,7);c.fill();c.stroke();
  c.beginPath();c.moveTo(-76,-64);c.lineTo(-96,-58);c.lineTo(-78,-52);c.closePath();c.fill();c.stroke();
  c.beginPath();c.moveTo(-60,-86);c.lineTo(-52,-104);c.lineTo(-44,-84);c.closePath();c.fill();c.stroke();
  for(const lx of [-34,-10,24,48]){c.beginPath();c.rect(lx-5,-30,10,34);c.fill();c.stroke()}
  c.beginPath();c.moveTo(60,-56);c.quadraticCurveTo(100,-70,96,-30);c.stroke();dot(-64,-72,3);c.restore()}
function lion(x,y,s=1,flip=1,col='#c8a05a'){c.save();c.translate(x,y);c.scale(s*flip,s);c.fillStyle=col;st(4);
  c.beginPath();c.ellipse(0,-58,72,34,0,0,7);c.fill();c.stroke();c.beginPath();c.arc(-70,-74,32,0,7);c.fill();c.stroke();c.fillStyle='#b78d45';c.beginPath();c.arc(-74,-74,22,0,7);c.fill();c.stroke();
  for(const lx of [-44,-14,30,56]){c.fillStyle=col;c.beginPath();c.rect(lx-6,-34,12,38);c.fill();c.stroke()}
  c.beginPath();c.moveTo(72,-64);c.quadraticCurveTo(116,-70,106,-24);c.stroke();dot(-82,-80,3);dot(-66,-80,3);c.restore()}
function bear(x,y,s=1,flip=1,col='#6a4a38'){c.save();c.translate(x,y);c.scale(s*flip,s);c.fillStyle=col;st(5);
  c.beginPath();c.ellipse(0,-120,120,84,0,0,7);c.fill();c.stroke();c.beginPath();c.ellipse(-110,-150,54,48,0,0,7);c.fill();c.stroke();
  c.beginPath();c.arc(-130,-192,16,0,7);c.arc(-90,-190,16,0,7);c.fill();c.stroke();
  for(const lx of [-70,-20,50,95]){c.beginPath();c.roundRect(lx-20,-70,40,74,12);c.fill();c.stroke()}
  c.fillStyle='#3a2518';c.beginPath();c.ellipse(-150,-142,18,14,0,0,7);c.fill();dot(-122,-160,5,'#fff');dot(-122,-160,2.5);c.restore()}

// ---- fire & shelter ----
function campfire(x,y,t,s=1,glowOn=true){c.save();c.translate(x,y);c.scale(s,s);if(glowOn){glow(0,-40,280,'255,170,60',.45)}
  st(7,'#4a2e1a');c.beginPath();c.moveTo(-50,0);c.lineTo(50,-18);c.moveTo(50,0);c.lineTo(-50,-18);c.stroke();
  const fl=(k,w,h,col)=>{c.fillStyle=col;c.beginPath();const sw=Math.sin(t*9+k)*6;c.moveTo(-w,0);c.quadraticCurveTo(-w*1.2+sw,-h*.5,sw*.6,-h);c.quadraticCurveTo(w*1.2+sw,-h*.5,w,0);c.closePath();c.fill()};
  fl(0,40,100,'#e8571d');fl(1.7,30,80,'#f89a1d');fl(3.1,18,56,'#ffe07a');
  for(let i=0;i<5;i++){const p=((t*.9+i/5)%1);c.fillStyle=`rgba(255,200,90,${1-p})`;c.beginPath();c.arc(Math.sin(i*3+t)*28,-70-p*110,3,0,7);c.fill()}c.restore()}
function bonehut(x,y,s=1,build=1,t=0){c.save();c.translate(x,y);c.scale(s,s);
  const n=Math.floor(22*build);c.lineWidth=2;for(let i=0;i<n;i++){const a=Math.PI+(i/21)*Math.PI,r=150+((i*7)%3)*6;const bx=Math.cos(a)*r,by=Math.sin(a)*r*.9;c.save();c.translate(bx,by);c.rotate(a+Math.PI/2);c.fillStyle=BONE;st(2.5,'#a89b7a');c.beginPath();c.roundRect(-34,-9,68,18,9);c.fill();c.stroke();c.restore()}
  if(build>.99){c.fillStyle=FUR;st(4,'#4a3321');c.beginPath();c.moveTo(-150,0);for(let i=0;i<=10;i++){const a=Math.PI+i/10*Math.PI;c.lineTo(Math.cos(a)*142,Math.sin(a)*132)}c.lineTo(150,0);c.closePath();c.fill();c.stroke();
    c.fillStyle='#2a1a10';c.beginPath();c.moveTo(-34,0);c.lineTo(-34,-58);c.quadraticCurveTo(0,-86,34,-58);c.lineTo(34,0);c.closePath();c.fill();
    c.fillStyle=BONE;for(let i=0;i<9;i++){const a=Math.PI+(i+.5)/9*Math.PI;c.save();c.translate(Math.cos(a)*140,Math.sin(a)*130);c.rotate(a+Math.PI/2);c.beginPath();c.roundRect(-26,-6,52,12,6);c.fill();c.restore()}}
  c.restore()}
function caveBG(t,o={}){c.fillStyle='#3b3340';c.fillRect(-300,-300,W+600,H+600);const g=c.createRadialGradient(o.fx||640,GY-60,40,o.fx||640,GY-60,820);g.addColorStop(0,'rgba(255,170,70,.55)');g.addColorStop(1,'rgba(20,10,30,.9)');c.fillStyle=g;c.fillRect(-300,-300,W+600,H+600);
  c.fillStyle='#2a2230';st(4,'#150f1a');c.beginPath();c.moveTo(-300,0);c.lineTo(W+300,0);c.lineTo(W+300,120);for(let x=W+300;x>=-300;x-=90)c.lineTo(x,150+((x*7)%60));c.closePath();c.fill();c.stroke();
  c.fillStyle='#4a3f4f';c.fillRect(-300,GY-8,W+600,H);c.strokeStyle='#150f1a';c.beginPath();c.moveTo(-300,GY-8);c.lineTo(W+300,GY-8);c.stroke()}
function caveWall(x,y,w,h){c.fillStyle='#b99870';st(5,'#6f5538');c.beginPath();c.roundRect(x,y,w,h,24);c.fill();c.stroke()}
function paintBison(x,y,s,col='#8a3b1f'){c.save();c.translate(x,y);c.scale(s,s);c.fillStyle=col;st(3,col);c.beginPath();c.ellipse(0,0,70,36,0,0,7);c.fill();c.beginPath();c.ellipse(-62,-18,40,32,0,0,7);c.fill();c.beginPath();c.arc(-92,-10,16,0,7);c.fill();for(const lx of [-40,-12,28,52]){c.beginPath();c.moveTo(lx,20);c.lineTo(lx-2,62);c.stroke()}c.restore()}
function handPrint(x,y,s=1,col='#8a3b1f'){c.save();c.translate(x,y);c.scale(s,s);c.fillStyle=col;c.beginPath();c.ellipse(0,10,22,26,0,0,7);c.fill();for(let i=0;i<5;i++){c.beginPath();c.ellipse((i-2)*12,-24-(i===0||i===4?-6:Math.abs(i-2)===0?10:0),5,16,(i-2)*.12,0,7);c.fill()}c.restore()}

// ---- objects & icons ----
function needle(x,y,s=1,rot=0,thread=0){c.save();c.translate(x,y);c.rotate(rot);c.scale(s,s);c.fillStyle=BONE;st(3,'#a89b7a');c.beginPath();c.moveTo(-140,-5);c.lineTo(110,-3);c.lineTo(140,0);c.lineTo(110,3);c.lineTo(-140,5);c.closePath();c.fill();c.stroke();
  c.fillStyle='#3d2e1f';c.beginPath();c.ellipse(-118,0,10,3,0,0,7);c.fill();if(thread>0){st(3,'#c0392b');c.beginPath();c.moveTo(-118,0);c.bezierCurveTo(-170,-20,-190,40,-240*thread,10);c.stroke()}c.restore()}
function thermometer(x,y,lvl,s=1){c.save();c.translate(x,y);c.scale(s,s);c.fillStyle='#fff';st(5);c.beginPath();c.roundRect(-18,-140,36,150,18);c.fill();c.stroke();c.beginPath();c.arc(0,22,32,0,7);c.fill();c.stroke();
  c.fillStyle=lvl<.4?'#3a8fd6':'#d63a3a';c.beginPath();c.arc(0,22,24,0,7);c.fill();const mh=lerp(14,138,lvl);c.fillRect(-8,22-mh,16,mh);
  st(3);for(let i=0;i<6;i++){c.beginPath();c.moveTo(18,-120+i*22);c.lineTo(32,-120+i*22);c.stroke()}c.restore()}
function clock(x,y,r,tm,s=1,hours=1){c.save();c.translate(x,y);c.scale(s,s);c.fillStyle='#fff';st(8);c.beginPath();c.arc(0,0,r,0,7);c.fill();c.stroke();
  st(4);for(let i=0;i<12;i++){const a=i/12*Math.PI*2;c.beginPath();c.moveTo(Math.sin(a)*r*.82,-Math.cos(a)*r*.82);c.lineTo(Math.sin(a)*r*.94,-Math.cos(a)*r*.94);c.stroke()}
  st(8);c.beginPath();c.moveTo(0,0);const ha=tm/12*Math.PI*2;c.lineTo(Math.sin(ha)*r*.5,-Math.cos(ha)*r*.5);c.stroke();st(5,RED);c.beginPath();c.moveTo(0,0);const ma=tm*Math.PI*2;c.lineTo(Math.sin(ma)*r*.8,-Math.cos(ma)*r*.8);c.stroke();dot(0,0,8);c.restore()}
function banner(text,y=360,sub,a=1,size=110,col='#fff',bg='rgba(14,22,54,.82)'){c.save();c.globalAlpha=a;c.fillStyle=bg;c.fillRect(-300,y-size*.85,W+600,size*(sub?1.9:1.3));txt(text,W/2,y+size*.12,size,col);if(sub)txt(sub,W/2,y+size*.12+size*.78,size*.42,'#ffd95a');c.restore()}
function stamp(text,x,y,s,col=RED,rot=-.12){at(x,y,s,()=>{c.fillStyle='rgba(255,255,255,.9)';st(8,col);c.beginPath();c.roundRect(-250,-62,500,124,18);c.fill();c.stroke();txt(text,0,26,70,col)},rot)}
function xMark(x,y,s,col=RED){cross(x,y,s,col)}
function noSign(x,y,s,fn){at(x,y,s,()=>{fn();c.strokeStyle=RED;c.lineWidth=18;c.lineCap='round';c.beginPath();c.arc(0,0,92,0,7);c.moveTo(-64,-64);c.lineTo(64,64);c.stroke()})}
function streetlamp(x,y,s=1){c.save();c.translate(x,y);c.scale(s,s);st(7,'#555');c.beginPath();c.moveTo(0,0);c.lineTo(0,-180);c.quadraticCurveTo(0,-210,30,-210);c.stroke();c.fillStyle='#ffe28a';st(4);c.beginPath();c.roundRect(14,-214,42,16,6);c.fill();c.stroke();c.restore()}
function phoneIcon(x,y,s=1,bars=0){c.save();c.translate(x,y);c.scale(s,s);c.fillStyle='#222';st(5);c.beginPath();c.roundRect(-44,-80,88,160,16);c.fill();c.stroke();c.fillStyle='#bfe3ff';c.beginPath();c.roundRect(-36,-66,72,128,8);c.fill();
  for(let i=0;i<4;i++){c.fillStyle=i<bars?'#2e9e4f':'#c7ced6';c.fillRect(-26+i*14,-30-i*10,10,20+i*10)}c.restore()}
function sparkleBurst(x,y,t,n=8,r=80,col='#fff3b0'){for(let i=0;i<n;i++){const a=i/n*Math.PI*2+t*2;sparkle(x+Math.cos(a)*r,y+Math.sin(a)*r*.8,8+5*Math.sin(t*5+i),col)}}
function stomach(x,y,s,t){c.save();c.translate(x,y);c.scale(s,s);for(let i=0;i<3;i++){c.strokeStyle=`rgba(214,40,40,${.5+.5*Math.sin(t*8+i)})`;c.lineWidth=6;c.lineCap='round';c.beginPath();c.arc(0,0,40+i*20,-.6,.6);c.stroke()}c.restore()}
function meatLeg(x,y,s=1,rot=0){at(x,y,s,()=>{c.fillStyle='#c0504d';st(4);c.beginPath();c.ellipse(0,0,50,34,0,0,7);c.fill();c.stroke();c.fillStyle=BONE;c.beginPath();c.roundRect(40,-10,60,20,10);c.fill();c.stroke();dot(104,0,12,BONE)},rot)}
function fatBlock(x,y,s=1){at(x,y,s,()=>{c.fillStyle='#fff3c4';st(4);c.beginPath();c.roundRect(-40,-28,80,56,14);c.fill();c.stroke();c.strokeStyle='rgba(200,170,80,.5)';c.lineWidth=3;c.beginPath();c.moveTo(-24,-8);c.lineTo(24,-8);c.moveTo(-24,12);c.lineTo(24,12);c.stroke()})}
function hideIcon(x,y,s=1){at(x,y,s,()=>{c.fillStyle=FUR;st(4);c.beginPath();c.moveTo(-60,-30);c.lineTo(-30,-44);c.lineTo(0,-34);c.lineTo(30,-44);c.lineTo(60,-30);c.lineTo(46,0);c.lineTo(62,34);c.lineTo(20,44);c.lineTo(-20,40);c.lineTo(-60,34);c.lineTo(-46,0);c.closePath();c.fill();c.stroke()})}
function boneIcon(x,y,s=1,rot=.4){at(x,y,s,()=>{c.fillStyle=BONE;st(4,'#8a7d5c');c.beginPath();c.roundRect(-64,-9,128,18,9);c.fill();c.stroke();c.beginPath();c.arc(-66,-10,12,0,7);c.arc(-66,10,12,0,7);c.arc(66,-10,12,0,7);c.arc(66,10,12,0,7);c.fill();c.stroke()},rot)}
function tusk(x,y,s=1,rot=0){at(x,y,s,()=>{c.strokeStyle='#f1ead2';c.lineWidth=22;c.lineCap='round';c.beginPath();c.moveTo(-80,40);c.quadraticCurveTo(-20,50,40,-10);c.quadraticCurveTo(70,-50,40,-80);c.stroke();c.strokeStyle=INK;c.lineWidth=3;c.beginPath();c.moveTo(-80,40);c.quadraticCurveTo(-20,50,40,-10);c.stroke()},rot)}
function spear(x,y,len,rot,s=1){c.save();c.translate(x,y);c.rotate(rot);c.scale(s,s);st(5,'#6a4a2c');c.beginPath();c.moveTo(-len/2,0);c.lineTo(len/2,0);c.stroke();c.fillStyle='#bfc5cc';c.beginPath();c.moveTo(len/2,0);c.lineTo(len/2-26,-9);c.lineTo(len/2+22,0);c.lineTo(len/2-26,9);c.closePath();c.fill();c.restore()}
function eyeBig(x,y,s,sq=0,t=0){at(x,y,s,()=>{c.fillStyle='#fff';st(8);c.beginPath();c.ellipse(0,0,150,lerp(100,22,sq),0,0,7);c.fill();c.stroke();c.fillStyle='#3a8fd6';c.beginPath();c.arc(0,0,lerp(60,24,sq),0,7);c.fill();dot(0,0,lerp(26,12,sq));dot(-16,-16,8,'#fff')})}
function sunStar(x,y,r,t){c.save();c.translate(x,y);c.rotate(t*.2);st(5,'#e0a800');c.fillStyle='#ffd84d';for(let i=0;i<12;i++){c.rotate(Math.PI/6);c.beginPath();c.moveTo(r*1.1,-8);c.lineTo(r*1.6,0);c.lineTo(r*1.1,8);c.closePath();c.fill();c.stroke()}c.beginPath();c.arc(0,0,r,0,7);c.fill();c.stroke();c.restore()}
function skullSafe(){} // no gore: danger shown with "!" and stars instead
function bang(x,y,s,col='#ffcc00'){at(x,y,s,()=>{c.fillStyle=col;st(5);c.beginPath();for(let i=0;i<16;i++){const a=i/16*Math.PI*2,r=i%2?44:72;c.lineTo(Math.cos(a)*r,Math.sin(a)*r)}c.closePath();c.fill();c.stroke();txt('!',0,24,70,RED)})}
function tuftGrass(x,y){st(3,'#9db8c9');for(let i=-2;i<=2;i++){c.beginPath();c.moveTo(x+i*5,y);c.quadraticCurveTo(x+i*7,y-14,x+i*12,y-28);c.stroke()}}
function frostBreath(x,y,t,dir=1){for(let i=0;i<4;i++){const p=((t*.7+i/4)%1);c.fillStyle=`rgba(255,255,255,${.7*(1-p)})`;c.beginPath();c.arc(x+dir*p*70,y-p*30,8+p*16,0,7);c.fill()}}
function bubbleThought(x,y,w,h,fn){c.save();c.translate(x,y);bubbleCloud(0,0,w,h,'r');fn&&fn();c.restore()}
function heartsUp(x,y,t,n=4){for(let i=0;i<n;i++){const p=((t*.5+i/n)%1);heart(x+Math.sin(t*3+i*2)*40+i*20-30,y-p*150,.55+.35*(1-p),RED)}}
function groupFamily(cx,t,o={}){hunter(cx-120,{flip:o.flip||1,face:{m:'smile'},...(o.h||{})});mama(cx,{flip:o.flip||1,...(o.m||{})});kid(cx+90,{flip:o.flip||1,...(o.k||{})})}
