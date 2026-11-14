// Ken Burns video from generated images (1920x1080)
const CW=1920,CH=1080,cv=document.getElementById('c');cv.width=CW;cv.height=CH;const MAIN=cv.getContext('2d');
const clamp=(x,a=0,b=1)=>Math.min(b,Math.max(a,x)),lerp=(a,b,t)=>a+(b-a)*t,ease=t=>{t=clamp(t);return t<.5?2*t*t:1-Math.pow(-2*t+2,2)/2};
const N=SCN.length;const IM=[];let loaded=0;
window.READY=new Promise(res=>{for(let i=0;i<N;i++){const im=new Image();im.onload=im.onerror=()=>{if(++loaded===N)res(true)};im.src='imgs/'+String(i+1).padStart(3,'0')+'.jpg';IM.push(im)}});
const LABELS={4:'HOW LONG WOULD YOU LAST?',5:'HOUR BY HOUR',6:'THE REAL ANSWER',7:'HOUR 1',8:'~25,000 YEARS AGO',10:'NORTHERN EUROPE',13:'T-SHIRT · JEANS · SNEAKERS',18:'NO SIGNAL · NO MAP · NO HELP',19:'VERDICT?',20:'IN TROUBLE',27:'BONE NEEDLES',37:'HOUR 3 · SHELTER',38:'WIND',43:'MAMMOTH-BONE HOMES',51:'NIGHT COMES',55:'FIRE',59:'NOT JUST A SPARK',69:'DAY 2 · WATER',77:'DAY 3 · FOOD',86:'MEAT · FAT · HIDE · BONE',92:'DAY 4 · YOUR EYES',93:'SNOW BLINDNESS',99:'WEEK 1 · PREDATORS',109:'WEEK 2 · GETTING SICK',110:'NO DOCTORS · NO HOSPITALS',119:'MONTH 1',132:'THE THING NOBODY TELLS YOU',140:'SO, HOW LONG WOULD YOU LAST?',141:'ALONE: HOURS, MAYBE DAYS',145:'YOUR TURN',147:'NEXT: WHEN THE FIRE WENT OUT'};
const SNOWY=new Set([0,1,2,3,8,9,12,13,14,17,18,20,21,22,38,39,40,70,71,72,79,80,81,82,83,84,85,86,92,93,94,95,98,100,101,102,103,104,139,146]);
function kb(i,u,dur){ // returns draw rect for image
  const p=clamp(u/dur),e=p;let z=1,ax=.5,ay=.5;const m=i%7;
  if(i===148){return[0,0,CW,CH]}
  const Z=0.10;
  if(m===0){z=1+Z*e;ax=.5;ay=.5}
  else if(m===1){z=1+Z*(1-e);ax=.5;ay=.5}
  else if(m===2){z=1+Z;ax=lerp(0,1,e);ay=.5}
  else if(m===3){z=1+Z;ax=lerp(1,0,e);ay=.5}
  else if(m===4){z=1+Z*e;ax=.28;ay=.4}
  else if(m===5){z=1+Z*e;ax=.72;ay=.5}
  else {z=1+Z;ax=.5;ay=lerp(0,1,e)}
  const w=CW*z,h=CH*z;return[-(w-CW)*ax,-(h-CH)*ay,w,h]}
function paint(ctx,i,t){const sc=SCN[i],u=t-sc[0],dur=Math.max(.6,sc[1]-sc[0]);ctx.clearRect(0,0,CW,CH);const r=kb(i,u,dur);
  ctx.drawImage(IM[i],r[0],r[1],r[2],r[3]);
  if(SNOWY.has(i)){ctx.fillStyle='rgba(255,255,255,.85)';for(let k=0;k<90;k++){const x=((k*97.3+t*(26+(k%5)*8))%2100)-90,y=((k*53.1+t*(70+(k%7)*12))%1250)-80;ctx.beginPath();ctx.arc(x,y,2+(k%3)*1.2,0,7);ctx.fill()}}
  const g=ctx.createRadialGradient(CW/2,CH/2,CH*.45,CW/2,CH/2,CH*1.05);g.addColorStop(0,'rgba(0,0,0,0)');g.addColorStop(1,'rgba(0,0,0,.28)');ctx.fillStyle=g;ctx.fillRect(0,0,CW,CH);
  const lab=LABELS[i];if(lab){const a=clamp(u/.25)*clamp((dur-u)/.2+.5);ctx.save();ctx.globalAlpha=Math.min(1,a);ctx.font='800 84px "Trebuchet MS","DejaVu Sans",Arial,sans-serif';ctx.textAlign='left';ctx.lineJoin='round';
    let s=lab,w=ctx.measureText(s).width;let fs=84;while(w>CW-140&&fs>40){fs-=4;ctx.font=`800 ${fs}px "Trebuchet MS","DejaVu Sans",Arial,sans-serif`;w=ctx.measureText(s).width}
    const y=118+(1-ease(u/.3))*-30;ctx.lineWidth=16;ctx.strokeStyle='#000';ctx.strokeText(s,70,y);ctx.fillStyle='#ffe14d';ctx.fillText(s,70,y);ctx.restore()}
  if(i===148){const a=ease(u/.5);ctx.save();ctx.globalAlpha=a;ctx.font='800 46px "Trebuchet MS","DejaVu Sans",Arial,sans-serif';ctx.textAlign='center';ctx.fillStyle='#fff';ctx.lineWidth=8;ctx.strokeStyle='#600';ctx.strokeText('SUBSCRIBE',CW*.83,CH*.545);ctx.fillText('SUBSCRIBE',CW*.83,CH*.545);ctx.restore()}}
const OFF1=document.createElement('canvas'),OFF2=document.createElement('canvas');OFF1.width=OFF2.width=CW;OFF1.height=OFF2.height=CH;const TR=.3;
function caption(t){let k=-1;for(let i=0;i<S.length;i++){if(t>=S[i]-.02)k=i;else break}if(k<0)return;const end=k+1<S.length?S[k+1]:428.2;if(t>end)return;
  const x=MAIN;x.save();x.font='800 42px "Trebuchet MS","DejaVu Sans",Arial,sans-serif';x.textAlign='center';x.lineJoin='round';const words=SENTS[k].split(' '),maxW=1650;let lines=[],cur='';
  for(const w of words){const tt=cur?cur+' '+w:w;if(x.measureText(tt).width>maxW){lines.push(cur);cur=w}else cur=tt}lines.push(cur);x.globalAlpha=clamp((t-S[k])/.12);
  lines.forEach((ln,j)=>{const y=CH-42-(lines.length-1-j)*54;x.lineWidth=12;x.strokeStyle='rgba(0,0,0,.92)';x.strokeText(ln,CW/2,y);x.fillStyle='#fff';x.fillText(ln,CW/2,y)});x.restore()}
function draw(t){let i=SCN.findIndex(s=>t>=s[0]&&t<s[1]);if(i<0)i=N-1;const u=t-SCN[i][0];
  if(i>0&&u<TR){const p=ease(u/TR),k=i%4;paint(OFF1.getContext('2d'),i-1,SCN[i-1][1]-.001);paint(OFF2.getContext('2d'),i,t);MAIN.clearRect(0,0,CW,CH);
    if(k===1){MAIN.drawImage(OFF1,-p*CW,0);MAIN.drawImage(OFF2,CW-p*CW,0)}
    else if(k===3){MAIN.drawImage(OFF1,0,0);MAIN.save();MAIN.beginPath();MAIN.arc(CW/2,CH/2,p*Math.hypot(CW,CH)/2,0,7);MAIN.clip();MAIN.drawImage(OFF2,0,0);MAIN.restore()}
    else{MAIN.drawImage(OFF1,0,0);MAIN.globalAlpha=p;MAIN.drawImage(OFF2,0,0);MAIN.globalAlpha=1}}
  else paint(MAIN,i,t);caption(t)}
window.draw=draw;window.DURATION=428.2;
