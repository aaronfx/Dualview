// ================= SCENES part 2: night, fire, water, food (2:23 - 4:21) =================
const nightBG=(t,o={})=>{skyFill('#0b1330','#1b2c5e');stars(t,70);if(o.moon!==false)moon(1040,150,50);c.fillStyle='#1d2b52';st(3,'#0b1330');c.beginPath();c.moveTo(-300,GY-70);[[-120,380],[120,260],[360,360],[600,240],[860,350],[1100,270],[1400,370]].forEach(p=>c.lineTo(p[0],p[1]));c.lineTo(1600,GY-70);c.closePath();c.fill();c.stroke();
  c.fillStyle='#2b3d70';c.fillRect(-300,GY-70,W+600,H);c.strokeStyle='#0b1330';c.beginPath();c.moveTo(-300,GY-70);c.lineTo(W+300,GY-70);c.stroke()};
add(T(55),T(56),'#f6b36a',(u,t)=>{const d=seg(u,0,1.7);skyFill(mix([246,170,100],[11,19,48],d),mix([253,224,170],[27,44,94],d));if(d>.4)stars(t,Math.floor(60*d));iceMountains(0,mix([214,170,150],[29,43,82],d));snowGround(GY-70,mix([255,236,210],[43,61,112],d));
  c.fillStyle=`rgba(255,200,90,${1-d})`;c.beginPath();c.arc(640,lerp(GY-120,GY+80,d),70,0,7);c.fill();shadow(300,GY);you(300,{face:{m:'worry'},hands:[[-12,-30],[14,-30]],coatCol:'#3b82d6'});
  at(900,150,pop(u,.4),()=>txt('NIGHT COMES',0,0,80,'#fff'))});
add(T(56),T(57),'#0b1330',(u,t)=>{nightBG(t,{moon:false});vignetteDark(.5);shadow(640,GY);you(640,{s:.6,face:{m:'worry',up:.3},hands:[[-12,-30],[14,-30]],lean:2+shiver(t,.4)});at(640,130,pop(u,.5),()=>txt('SO DARK',0,0,90,'#fff'))});
add(T(57),T(59),'#0b1330',(u,t)=>{nightBG(t);vignetteDark(.3);noSign(340,330,1.3*pop(t,T(57),.3),()=>streetlamp(-10,70,1.0));noSign(940,330,1.3*pop(t,T(58),.3),()=>phoneIcon(0,0,.9,4));
  at(340,590,pop(t,T(57),.3),()=>txt('NO STREETLIGHTS',0,0,40,'#fff'));at(940,590,pop(t,T(58),.3),()=>txt('NO GLOWING SCREENS',0,0,40,'#fff'))});
add(T(59),T(60),'#0b1330',(u,t)=>{nightBG(t);const sx=lerp(1200,200,lin(u,.3,1.0)),sy=lerp(60,260,lin(u,.3,1.0));if(u>.3&&u<1.1){st(4,'#fff');c.beginPath();c.moveTo(sx,sy);c.lineTo(sx+120,sy-50);c.stroke()}
  shadow(500,GY);you(500,{s:.6,face:{m:'o',mo:.2,up:.6},tilt:-.4,hands:[[-12,-30],[14,-30]]});at(900,560,pop(u,.8),()=>txt('...A SILENCE THAT FEELS HEAVY',0,0,44,'#cfd8ff'))});
add(T(60),T(61),'#0b1330',(u,t)=>{nightBG(t,{moon:false});campfire(W/2,GY-10,t,1.7);at(W/2,110,pop(u,.3),()=>txt('FIRE IS EVERYTHING',0,0,90,'#ffd95a'))});
add(T(61),T(61)+1.4,'#0b1330',(u,t)=>{nightBG(t,{moon:false});campfire(380,GY-10,t,1.1);hunter(760,{flip:-1,face:{m:'smile'},hands:[[-12,-30],[14,-30]]});shadow(760,GY);
  for(let i=0;i<4;i++){const p=((t*.8+i/4)%1);c.strokeStyle=`rgba(255,150,70,${.6*(1-p)})`;c.lineWidth=6;c.beginPath();c.arc(560,GY-120,60+p*160,-.5,.5);c.stroke()}at(W/2,110,pop(u,.2),()=>txt('WARMS YOU',0,0,80,'#ffd95a'))});
add(T(61)+1.4,T(63),'#0b1330',(u,t)=>{nightBG(t,{moon:false});campfire(W/2,GY-10,t,1.1);c.save();c.translate(W/2,GY-200);c.strokeStyle='#6a4a2c';c.lineWidth=7;c.beginPath();c.moveTo(-160,40);c.lineTo(160,40);c.stroke();c.restore();
  meatLeg(W/2-60,GY-170,1.0,.25+Math.sin(t*3)*.03);meatLeg(W/2+90,GY-170,.9,-.3);at(W/2,100,pop(u,.2),()=>txt('COOKS YOUR FOOD',0,0,80,'#ffd95a'))});
add(T(63),T(64),'#0b1330',(u,t)=>{nightBG(t,{moon:false});campfire(380,GY-10,t,1.1);const k=lin(u,0,1.7);[0,1,2].forEach(i=>{eyesDark(lerp(760+i*160,1180+i*80,k),GY-120-i*30,1,'#ffe14d')});wolf(lerp(1000,1380,k),GY,.8,-1,'#4a5560');
  mama(560,{flip:1,face:{m:'smile'},hands:[[-12,-30],[14,-30]]});shadow(560,GY);at(W/2,100,pop(u,.1),()=>txt('KEEPS ANIMALS AWAY',0,0,76,'#ffd95a'))});
add(T(64),T(65),'#0b1330',(u,t)=>{nightBG(t,{moon:false});st(7,'#6a4a2c');c.beginPath();c.moveTo(500,GY-30);c.lineTo(780,GY-60);c.stroke();for(let i=0;i<10;i++){const p=((t*1.6+i/10)%1);sparkle(640+Math.sin(i*5)*30,GY-70-p*120,5+4*(1-p),'#ffd95a')}
  at(W/2,160,pop(u,.1),()=>txt('NOT JUST A SPARK',0,0,96,'#fff'));cross(W/2+360,300,.8*pop(u,.9),RED)});
add(T(65),T(65)+2.7,'#0b1330',(u,t)=>{nightBG(t,{moon:false});snowGround(GY-70,'#35487f');tuftGrass(300,GY-30);tuftGrass(900,GY-24);st(5,'#6a4a2c');c.beginPath();c.moveTo(560,GY-24);c.lineTo(700,GY-36);c.stroke();
  at(W/2,130,pop(u,.2),()=>txt('DRY FUEL IS RARE',0,0,76,'#fff'));at(W/2,230,pop(u,.9),()=>txt('WOOD IS SCARCE',0,0,56,'#ffd95a'));shadow(1000,GY);you(1000,{flip:-1,s:.7,face:{m:'worry'},hands:[[-12,-30],[14,-30]]})});
add(T(65)+2.7,T(66),'#0b1330',(u,t)=>{nightBG(t,{moon:false});c.fillStyle='rgba(190,225,245,.9)';st(4,'#7fb3d0');for(let i=0;i<6;i++){c.beginPath();c.roundRect(240+i*150,GY-60-(i%2)*20,110,36,10);c.fill();c.stroke()}
  at(W/2,160,pop(u,.1),()=>txt('EVERYTHING IS FROZEN',0,0,76,'#9fd8ff'));st(6,'#6a4a2c');c.beginPath();c.moveTo(420,GY-120);c.lineTo(640,GY-140);c.stroke();snowfall(t,40)});
add(T(66),T(66)+3.5,'#0b1330',(u,t)=>{nightBG(t,{moon:false});c.fillStyle='#3d2f26';st(4);c.beginPath();c.ellipse(W/2,GY-40,260,56,0,0,7);c.fill();c.stroke();campfire(W/2,GY-50,t,1.0);boneIcon(W/2-120,GY-70,.7,.2);boneIcon(W/2+110,GY-70,.7,-.3);fatBlock(W/2+10,GY-60,.7);
  at(W/2,120,pop(u,.2),()=>txt('BONES AND ANIMAL FAT',0,0,76,'#ffd95a'));at(W/2,200,pop(u,.8),()=>txt('BURNED FOR FUEL',0,0,52,'#fff'))});
add(T(66)+3.5,T(67),'#0b1330',(u,t)=>{nightBG(t,{moon:false});const p=t*4;const x=lerp(180,1000,lin(u,0,3.8));shadow(x,GY);hunter(x,{flip:1,feet:walkFeet(p,16,7),hands:[[-6,-40],[30,-60]],face:{m:'smile'}});
  at(x+90,GY-190,1,()=>{c.fillStyle='#6a4a2c';st(4);c.beginPath();c.moveTo(-26,0);c.quadraticCurveTo(0,40,26,0);c.closePath();c.fill();c.stroke();glow(0,-8,60,'255,150,50',.7);c.fillStyle='#ff9a2e';c.beginPath();c.arc(0,-6,12,0,7);c.fill()});
  tuftGrass(1100,GY-30);at(W/2,110,pop(u,.2),()=>txt('CARRYING EMBERS',0,0,70,'#ffd95a'));at(W/2,180,pop(u,.8),()=>txt('CAMP TO CAMP',0,0,48,'#fff'))});
add(T(67),T(69),'#0b1330',(u,t)=>{nightBG(t,{moon:false});shadow(540,GY);you(540+Math.sin(t*20)*3,{face:{m:'grin'},hipY:-30,feet:[[-14,0],[14,0]],hands:[[34,-30],[26,-28+Math.sin(t*20)*6]],lean:10});
  st(7,'#6a4a2c');c.beginPath();c.moveTo(600,GY-60);c.lineTo(760,GY-62);c.stroke();for(let i=0;i<3;i++){c.fillStyle=`rgba(190,190,190,${.5-.15*i})`;c.beginPath();c.arc(690+Math.sin(t*2+i)*8,GY-100-i*50,20+i*10,0,7);c.fill()}
  at(960,150,pop(u,.3),()=>txt('YOU? ONE HOUR OF RUBBING...',0,0,46,'#fff'));if(t>T(68)+2.2)at(960,420,pop(t,T(68)+2.2,.3),()=>{c.fillStyle='#f2a0a0';st(4);c.beginPath();c.ellipse(0,0,40,26,0,0,7);c.fill();c.stroke();txt('BLISTER',0,70,36,'#ffb0b0')})});
add(T(69),T(71),'#0b1330',(u,t)=>{nightBG(t);vignetteDark(.25);shadow(640,GY);you(640,{s:.8,face:{m:'sad'},hipY:-26,feet:[[-18,0],[26,0]],hands:[[34,-30],[24,-26]],lean:18,coatCol:'#8fb8e0'});
  stamp('PROBABLY NOT',640,200,pop(u,.8,.3),RED);at(640,640,pop(u,.2),()=>txt('VERDICT?',0,0,60,'#ffd95a'))});

// --- rescued; water
add(T(71),T(72),'#0b1330',(u,t)=>{nightBG(t);vignetteDark(.2);shadow(640,GY);you(640,{s:.8,face:{m:'sad',up:.2},hipY:-26,feet:[[-18,0],[26,0]],hands:[[34,-30],[24,-26]],lean:18});sparkleBurst(640,GY-250,t,8,150,'#ffd95a');at(640,110,pop(u,.3),()=>txt('BUT SAY YOU ARE LUCKY...',0,0,60,'#ffd95a'))});
add(T(72),T(73),'#0b1330',(u,t)=>{nightBG(t);const x=lerp(1500,980,seg(u,0,2));shadow(640,GY);you(640,{s:.8,flip:1,face:{m:'o',mo:.4},hipY:-26,feet:[[-18,0],[26,0]],hands:[[34,-30],[24,-26]],lean:14});
  const p=t*5;[[x,hunter],[x+110,mama],[x+210,kid]].forEach(([xx,f],i)=>{shadow(xx,GY);f(xx,{flip:-1,feet:u<2?walkFeet(p+i,16,7):undefined,hands:[[-6,-40],[26,-60]],face:{m:'smile'}})});glow(980,GY-200,300,'255,170,60',.25)});
add(T(73),T(74),'#0b1330',(u,t)=>{nightBG(t);campfire(W/2,GY-10,t,1.1);shadow(460,GY);you(460,{flip:1,face:{m:'smile'},hands:[[-12,-30],[14,-30]],hipY:-30,feet:[[-14,0],[18,0]]});hunter(820,{flip:-1,hands:[[-12,-30],[22,-60]]});shadow(820,GY);mama(930,{flip:-1});
  at(W/2,110,pop(u,.3),()=>txt('NOW THE REAL WORK BEGINS',0,0,60,'#ffd95a'))});
add(T(74),T(76),'#14224a',(u,t)=>{if(t<T(75)){card(u,t,'DAY 2');clock(W/2,540,80,2/12+u*.01,1)}else{card(t-T(75),t,'WATER');at(W/2,540,pop(t,T(75),.4),()=>{c.fillStyle='#4aa3df';st(6);c.beginPath();c.moveTo(0,-120);c.quadraticCurveTo(100,10,0,70);c.quadraticCurveTo(-100,10,0,-120);c.fill();c.stroke()})}});
add(T(76),T(77),'#cfe8f5',(u,t)=>{outdoor(t);shadow(560,GY);you(560,{face:{m:'sad',up:.1},hands:[[-12,-30],[16,-50-Math.sin(u*4)*3]],lean:3});at(900,200,pop(u,.3),()=>{bubbleCloud(0,0,140,86,'l');c.save();c.scale(1,1);c.fillStyle='#4aa3df';st(3);c.beginPath();c.moveTo(0,-30);c.quadraticCurveTo(26,4,0,26);c.quadraticCurveTo(-26,4,0,-30);c.fill();c.stroke();c.restore()});at(900,380,pop(u,.8),()=>txt('THIRSTY',0,0,70,'#2f6fb0'))});
add(T(77),T(78),'#cfe8f5',(u,t)=>{skyFill('#cfe8f5','#eef7fc');iceMountains(0);c.fillStyle='#d9f0fb';st(3,'#7fb3d0');c.fillRect(-300,GY-70,W+600,H);for(let i=0;i<8;i++){c.beginPath();c.moveTo(i*180-60,GY-70);c.lineTo(i*180-100,H);c.stroke()}
  shadow(300,GY);you(300,{s:.55,face:{m:'sad'},hands:[[-12,-30],[14,-30]]});at(W/2+160,150,pop(u,.4),()=>txt('A WORLD OF FROZEN WATER',0,0,56,'#17213f'));snowfall(t,40)});
add(T(78),T(80),'#cfe8f5',(u,t)=>{outdoor(t,{n:30});shadow(520,GY);const e=Math.abs(Math.sin(u*2.2));you(520,{face:{m:t<T(79)?'smile':'worry',brow:t<T(79)?0:-1},hands:[[-12,-30],[lerp(20,34,e),lerp(-50,-92,e)]],lean:2});
  if(t<T(79))at(900,260,pop(u,.3),()=>txt('SO YOU EAT SOME SNOW',0,0,52,'#17213f'));else{stamp('BAD IDEA',900,230,pop(t,T(79),.3),RED)}});
add(T(80),T(81),'#14224a',(u,t)=>{skyFill('#14224a','#23366e');c.save();c.translate(W/2-160,H/2+20);c.fillStyle='#f2c49b';st(6);c.beginPath();c.ellipse(0,0,120,220,0,0,7);c.fill();c.stroke();const lv=seg(u,0,2.6);c.save();c.beginPath();c.ellipse(0,0,112,212,0,0,7);c.clip();c.fillStyle='rgba(58,143,214,.75)';c.fillRect(-120,220-lv*430,240,430);c.restore();c.restore();
  thermometer(W/2+260,H/2,lerp(.8,.15,seg(u,0,2.6)),1.5);at(W/2,90,pop(u,.3),()=>txt('SNOW COOLS YOU FROM INSIDE',0,0,52,'#fff'))});
add(T(81),T(82),'#0b1330',(u,t)=>{nightBG(t,{moon:false});campfire(W/2,GY-10,t,1.1);st(6,'#6a4a2c');c.beginPath();c.moveTo(W/2-140,GY-230);c.lineTo(W/2+140,GY-230);c.stroke();
  c.fillStyle='#8a6a48';st(5);c.beginPath();c.roundRect(W/2-90,GY-290,180,90,18);c.fill();c.stroke();c.fillStyle='#e8f6ff';c.beginPath();c.ellipse(W/2,GY-290,86,16,0,0,7);c.fill();c.stroke();
  for(let i=0;i<5;i++){const p=((t*.6+i/5)%1);c.fillStyle=`rgba(255,255,255,${.5*(1-p)})`;c.beginPath();c.arc(W/2+Math.sin(i*3+t)*30,GY-310-p*110,14+p*10,0,7);c.fill()}at(W/2,90,pop(u,.3),()=>txt('MELT IT FIRST',0,0,76,'#ffd95a'))});
add(T(82),T(84),'#0b1330',(u,t)=>{nightBG(t,{moon:false});campfire(420,GY-10,t,1.0);const f=lerp(.9,.1,seg(t,T(82),T(84)));c.fillStyle='#fff';st(8);c.beginPath();c.roundRect(760,300,300,60,14);c.fill();c.stroke();c.fillStyle=f>.4?'#e8942e':'#d62828';c.beginPath();c.roundRect(770,310,Math.max(10,280*f),40,8);c.fill();txt('FUEL',910,270,44,'#fff');
  at(W/2,100,pop(u,.2),()=>txt(t<T(83)?'MELTING SNOW TAKES FUEL':'FUEL IS HARD TO FIND',0,0,58,'#ffd95a'))});
add(T(84),T(85),'#cfe8f5',(u,t)=>{outdoor(t,{n:30});const p=t*4;const x=lerp(260,980,lin(u,0,3.4));shadow(x,GY);hunter(x,{flip:1,feet:walkFeet(p,16,7),hands:[[-6,-40],[26,-70]],face:{m:'smile'}});
  at(x+80,GY-230,1,()=>{c.fillStyle='#e8d0a8';st(4);c.beginPath();c.ellipse(0,0,40,50,0,0,7);c.fill();c.stroke();c.fillStyle='#fff';c.beginPath();c.arc(0,-50,18,0,7);c.fill();c.stroke()});at(W/2,110,pop(u,.3),()=>txt('A SIMPLE DRINK BECOMES A JOB',0,0,56,'#17213f'))});

// --- food
add(T(85),T(87),'#14224a',(u,t)=>{if(t<T(86)){card(u,t,'DAY 3');clock(W/2,540,80,3/12+u*.01,1)}else{card(t-T(86),t,'FOOD');at(W/2,540,pop(t,T(86),.4),()=>meatLeg(0,0,2.2,.2))}});
add(T(87),T(88),'#cfe8f5',(u,t)=>{skyFill('#eaf1f6','#fff');c.save();c.translate(W/2,H/2+20);c.fillStyle='#fff';st(8,'#555');c.beginPath();c.roundRect(-190,-60,320,130,12);c.fill();c.stroke();st(8,'#555');c.beginPath();c.moveTo(-210,-110);c.lineTo(-190,-60);c.stroke();dot(-130,110,20,'#555');dot(70,110,20,'#555');
  c.strokeStyle='#999';c.lineWidth=4;for(let i=0;i<4;i++){c.beginPath();c.moveTo(-160+i*80,-60);c.lineTo(-160+i*80,70);c.stroke()}c.restore();cross(W/2,H/2+10,1.7*pop(u,.4),RED);at(W/2,110,pop(u,.2),()=>txt('NO SUPERMARKETS',0,0,76,'#17213f'))});
add(T(88),T(89),'#cfe8f5',(u,t)=>{outdoor(t,{n:30});tuftGrass(200,GY-30);tuftGrass(330,GY-34);at(W/2,110,pop(u,.1),()=>txt('PLANTS ARE SCARCE',0,0,70,'#17213f'));
  at(300,400,pop(u,1.6),()=>meatLeg(0,0,1.7,.2));at(640,400,pop(u,2.1),()=>fatBlock(0,0,1.9));at(980,420,pop(u,2.6),()=>{txt('MEAT + FAT',0,0,70,'#b5651d')});sparkleBurst(470,400,t,8,170)});
add(T(89),T(90),'#cfe8f5',(u,t)=>{outdoor(t,{n:30});mammoth(900,GY-50,.9,-1,t);const x=lerp(300,380,seg(u,0,2));shadow(x,GY);hunter(x,{face:{m:'worry',up:.3},hands:[[-12,-30],[24,-50]],feet:[[-12,0],[14,0]]});spear(x+70,GY-170,170,-.7);
  at(300,100,pop(u,.4),()=>txt('ONE MAN?',0,0,80,'#17213f'));cross(640,300,1.0*pop(u,1.6),RED)});
add(T(90),T(91),'#cfe8f5',(u,t)=>{outdoor(t,{n:30});mammoth(900,GY-50,.9,-1,t);[[220,hunter],[340,mama],[460,hunter]].forEach(([x,f],i)=>{shadow(x,GY);f(x,{flip:1,s:.85,hands:[[-12,-30],[24,-50]],face:{m:'flat'}});spear(x+66,GY-150,150,-.7)});
  at(300,100,pop(u,.4),()=>txt('A GROUP, A PLAN, PATIENCE',0,0,54,'#17213f'));check(640,300,.9*pop(u,1.6))});
add(T(91),T(91)+2.7,'#cfe8f5',(u,t)=>{skyFill('#cfe8f5','#eef7fc');c.fillStyle='#9fb6c4';st(4);c.beginPath();c.moveTo(-100,GY-70);c.lineTo(-100,300);c.lineTo(560,300);c.lineTo(560,GY-70);c.closePath();c.fill();c.stroke();snowGround();
  [[160,hunter],[290,mama]].forEach(([x,f])=>{shadow(x,300+30);f(x,{y:318,s:.6,flip:1,face:{m:'flat'},hands:[[-12,-30],[24,-60]]})});
  for(let i=0;i<4;i++)mammoth(760+i*170-u*40,GY-50+(i%2)*10,.32,-1,t+i);at(900,110,pop(u,.3),()=>txt('READING THE LAND',0,0,60,'#17213f'))});
add(T(91)+2.7,T(92),'#cfe8f5',(u,t)=>{skyFill('#cfe8f5','#eef7fc');snowGround();c.fillStyle='#8a8d96';st(4);c.beginPath();c.moveTo(900,GY-70);c.lineTo(900,300);c.lineTo(1300,300);c.lineTo(1300,GY-70);c.closePath();c.fill();c.stroke();
  const x=lerp(260,820,seg(u,0,2.2));mammoth(x,GY-50,.55,1,t);c.fillStyle='#3a2a1c';c.beginPath();c.ellipse(840,GY-60,100,16,0,0,7);c.fill();at(W/2,110,pop(u,.3),()=>txt('TRAPS AND TERRAIN',0,0,60,'#17213f'))});
add(T(92),T(93),'#cfe8f5',(u,t)=>{outdoor(t,{n:30});const x=lerp(1000,760,seg(u,0,1.4));mammoth(x,GY-50,1.0,-1,t);const hx=lerp(360,330,Math.sin(u*5)*.5+.5);shadow(hx,GY);hunter(hx,{face:{m:'o',mo:.5},hands:[[-12,-60],[22,-80]],lean:-6});
  if(u>1.2)bang(560,240,pop(u,1.2,.3));at(W/2,100,pop(u,.2),()=>txt('ONE MISTAKE...',0,0,76,'#b5251d'))});
add(T(93),T(94),'#fbe3b8',(u,t)=>{skyFill('#f6d9a8','#fdf0d4');snowGround(GY-70,'#fff7ea');[[300,hunter],[470,mama],[640,hunter],[800,kid]].forEach(([x,f],i)=>{shadow(x,GY);f(x,{face:{m:'grin'},hands:[[-12,-90+Math.sin(u*5+i)*10],[16,-96+Math.cos(u*5+i)*10]]})});
  c.fillStyle='#6b4a35';c.beginPath();c.ellipse(1040,GY-30,130,50,0,0,7);c.fill();at(W/2,100,pop(u,.3),()=>txt('THE HUNT WORKED',0,0,76,'#b5651d'));sparkleBurst(W/2,300,t,10,400)});
add(T(94),T(98),'#fbe3b8',(u,t)=>{skyFill('#f6d9a8','#fdf0d4');const it=(f,x,s,tm)=>{if(t>=tm)at(x,330,pop(t,tm,.3),()=>{f();txt(s,0,170,44,'#17213f')})};
  it(()=>meatLeg(0,0,1.4,.2),180,'MEAT',T(94));it(()=>fatBlock(0,0,1.8),460,'FAT',T(95));it(()=>hideIcon(0,0,1.7),740,'HIDE',T(96));it(()=>boneIcon(0,0,1.6,.4),1020,'BONE',T(97));at(W/2,110,pop(u,.1),()=>txt('NOTHING WASTED',0,0,80,'#b5651d'))});
add(T(98),T(99),'#fbe3b8',(u,t)=>{skyFill('#f6d9a8','#fdf0d4');tusk(W/2-160,420,2.0,-.5);tusk(W/2+160,420,-2.0,.5);c.save();c.translate(W/2,330);for(let i=0;i<3;i++){c.fillStyle='#d6c28a';c.beginPath();c.roundRect(-50+i*50,-20,36,80,8);c.fill();c.stroke()}c.restore();at(W/2,120,pop(u,.3),()=>txt('TUSKS BECAME TOOLS AND ART',0,0,56,'#17213f'))});
add(T(99),T(100),'#cfe8f5',(u,t)=>{skyFill('#cfe8f5','#eef7fc');snowGround();c.fillStyle='#bfe0f0';st(4,'#5d8fae');c.beginPath();c.ellipse(W/2,GY-20,300,70,0,0,7);c.fill();c.stroke();meatLeg(W/2-100,GY-60,1.1,.1);meatLeg(W/2+90,GY-56,1.0,-.2);snowfall(t,50);at(W/2,110,pop(u,.3),()=>txt('FOOD CAN BE KEPT FROZEN',0,0,60,'#17213f'))});
add(T(100),T(101),'#cfe8f5',(u,t)=>{skyFill('#bfe0f0','#e6f4fb');glacier(-60,GY-60,1400,330);c.fillStyle='#1d3a52';c.beginPath();c.ellipse(W/2,GY-70,240,120,0,Math.PI,0);c.fill();meatLeg(W/2-100,GY-100,1.0,.1);fatBlock(W/2+60,GY-100,1.0);boneIcon(W/2+170,GY-104,.8,.1);snowGround();at(W/2,100,pop(u,.3),()=>txt('THE ICE: A NATURAL FREEZER',0,0,60,'#17213f'))});
add(T(101),T(102),'#cfe8f5',(u,t)=>{outdoor(t);shadow(540,GY);you(540,{face:{m:'sad',up:.2},hands:[[-12,-30],[22,-30+Math.sin(t*10)*2]],lean:4+Math.sin(t*10)*.5});stomach(560,GY-240,1.0,t);at(900,230,pop(u,.4),()=>txt('HUNGRY',0,0,90,'#b5251d'))});
add(T(102),T(103),'#cfe8f5',(u,t)=>{outdoor(t);hunter(300,{flip:1,face:{m:'flat'},hands:[[-12,-30],[24,-50]]});mama(440,{flip:1,face:{m:'flat'}});shadow(300,GY);shadow(440,GY);shadow(780,GY);you(780,{flip:-1,face:{m:'worry',up:.3},hands:[[-12,-30],[16,-20]],lean:3});
  at(W/2,110,pop(u,.4),()=>txt('NOT MUCH HELP',0,0,76,'#17213f'))});
