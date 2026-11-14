const CW=1920,CH=1080,cv=document.getElementById('c');cv.width=CW;cv.height=CH;const MAIN=cv.getContext('2d');
const clamp=(x,a=0,b=1)=>Math.min(b,Math.max(a,x)),lerp=(a,b,t)=>a+(b-a)*t,ease=t=>{t=clamp(t);return t<.5?2*t*t:1-Math.pow(-2*t+2,2)/2};
const FONT='"Trebuchet MS","DejaVu Sans",Arial,sans-serif';
const COL={bg:'#0a1222',panel:'#0d1b30',chip:'#12294a',grid:'#14253f',up:'#2db3a6',dn:'#e24163',gold:'#e6b85c',white:'#ebf2fe',gray:'#8b9bb4'};
const IM={};let loaded=0;const NEED=SC.filter(s=>s.type==='F').length;
window.READY=new Promise(res=>{SC.forEach(s=>{if(s.type!=='F')return;const im=new Image();im.onload=im.onerror=()=>{if(++loaded===NEED)res(true)};im.src='imgs/'+String(s.k).padStart(3,'0')+'.jpg';IM[s.k]=im})});
const IDX={};SC.forEach((s,i)=>IDX[s.k]=i);
// per chart: ordered beat scenes
const CHBEATS={};Object.keys(CHARTS).forEach(id=>{CHBEATS[id]=Object.keys(CHARTS[id].beats).map(Number).sort((a,b)=>a-b)});
const PLOT={x:110,y:350,w:1450,h:500},PANEL={x:80,y:310,w:1760,h:570};
function sceneAt(t){let lo=0,hi=SC.length-1;while(lo<hi){const m=(lo+hi+1)>>1;if(SC[m].a<=t)lo=m;else hi=m-1}return lo}
function kbRect(i,u,dur,img){const p=clamp(u/dur);const m=i%7,Z=.10;let z=1,ax=.5,ay=.5;
 if(m===0){z=1+Z*p}else if(m===1){z=1+Z*(1-p)}else if(m===2){z=1+Z;ax=lerp(0,1,p)}else if(m===3){z=1+Z;ax=lerp(1,0,p)}else if(m===4){z=1+Z*p;ax=.28;ay=.4}else if(m===5){z=1+Z*p;ax=.72;ay=.5}else{z=1+Z;ay=lerp(0,1,p)}
 const iw=img.naturalWidth||1672,ih=img.naturalHeight||941,base=Math.max(CW/iw,CH/ih),w=iw*base*z,h=ih*base*z;return[-(w-CW)*ax,-(h-CH)*ay,w,h]}
function outlined(ctx,s,x,y,fs,fill,stroke,lw,align){ctx.font=`800 ${fs}px ${FONT}`;ctx.textAlign=align||'left';ctx.lineJoin='round';ctx.lineWidth=lw;ctx.strokeStyle=stroke;ctx.strokeText(s,x,y);ctx.fillStyle=fill;ctx.fillText(s,x,y)}
function paintFigure(ctx,i,t){const s=SC[i],u=t-s.a,dur=Math.max(.6,s.b-s.a);ctx.clearRect(0,0,CW,CH);const r=kbRect(s.k,u,dur,IM[s.k]);ctx.drawImage(IM[s.k],r[0],r[1],r[2],r[3]);
 const g=ctx.createRadialGradient(CW/2,CH/2,CH*.45,CW/2,CH/2,CH*1.05);g.addColorStop(0,'rgba(0,0,0,0)');g.addColorStop(1,'rgba(0,0,0,.26)');ctx.fillStyle=g;ctx.fillRect(0,0,CW,CH);
 if(s.label){const a=clamp(u/.25)*clamp((dur-u)/.2+.5);ctx.save();ctx.globalAlpha=Math.min(1,a);let fs=84;ctx.font=`800 ${fs}px ${FONT}`;while(ctx.measureText(s.label).width>CW-140&&fs>40){fs-=4;ctx.font=`800 ${fs}px ${FONT}`}
  outlined(ctx,s.label,70,118+(1-ease(u/.3))*-30,fs,'#ffe14d','#000',16,'left');ctx.restore()}}
// ---------- chart ----------
function chartView(s,t){const ch=CHARTS[SCH[s.k]];const bs=CHBEATS[SCH[s.k]];const bi=bs.indexOf(s.k);const prev=bi>0?ch.beats[bs[bi-1]].upto:0,cur=ch.beats[s.k].upto;const dur=Math.max(.6,s.b-s.a),u=t-s.a;
 const p=ease(clamp(u/(dur*.82)));return{ch,beat:ch.beats[s.k],v:prev+(cur-prev)*p}}
function yOf(ch,p){return PLOT.y+(ch.ymax-p)/(ch.ymax-ch.ymin)*PLOT.h}
function xOf(ch,i){return PLOT.x+(i+.5)*PLOT.w/ch.candles.length}
function pill(ctx,txt,x,y,col,alpha){ctx.save();ctx.globalAlpha=alpha;ctx.font=`800 22px ${FONT}`;const w=ctx.measureText(txt).width+26;ctx.fillStyle='rgba(10,18,34,.92)';ctx.strokeStyle=col;ctx.lineWidth=2;ctx.beginPath();ctx.roundRect(x-w/2,y-19,w,38,8);ctx.fill();ctx.stroke();ctx.fillStyle=col;ctx.textAlign='center';ctx.fillText(txt,x,y+8);ctx.restore()}
function annAlpha(a,s,v,t){let al=1;if(a.idx!==undefined&&typeof a.idx==='number')al=Math.min(al,clamp((v-a.idx)/2.5));if(a.scene!==undefined&&a.scene===s.k)al=Math.min(al,clamp((t-s.a)/.6));return al}
function annOn(a,s,v){if(a.scene!==undefined&&s.k<a.scene)return false;if(a.until!==undefined&&s.k>=a.until)return false;if(typeof a.idx==='number'&&v<a.idx)return false;return true}
function paintChart(ctx,i,t){const s=SC[i],{ch,beat,v}=chartView(s,t);ctx.clearRect(0,0,CW,CH);ctx.fillStyle=COL.bg;ctx.fillRect(0,0,CW,CH);
 // header
 ctx.font=`800 26px ${FONT}`;ctx.textAlign='left';ctx.fillStyle=COL.white;ctx.fillText('GOPIPWAYS',80,62);ctx.font=`700 20px ${FONT}`;ctx.textAlign='right';ctx.fillStyle=COL.gray;ctx.fillText('CHART STUDY',1840,60);ctx.fillStyle='#1b2a44';ctx.fillRect(80,80,1760,2);
 const ta=clamp((t-s.a)/.35);ctx.save();ctx.globalAlpha=ta;ctx.textAlign='left';ctx.fillStyle=COL.white;let fs=72;ctx.font=`800 ${fs}px ${FONT}`;while(ctx.measureText(beat.title).width>1760&&fs>40){fs-=4;ctx.font=`800 ${fs}px ${FONT}`}ctx.fillText(beat.title,80,170+(1-ta)*14);
 ctx.font=`500 30px ${FONT}`;ctx.fillStyle=COL.gray;ctx.fillText(beat.sub,80,218);ctx.restore();
 ctx.fillStyle=COL.chip;ctx.beginPath();ctx.roundRect(80,244,1760,46,8);ctx.fill();ctx.font=`800 22px ${FONT}`;ctx.fillStyle=COL.gold;ctx.textAlign='left';ctx.fillText(beat.chip,100,275);
 ctx.fillStyle=COL.panel;ctx.beginPath();ctx.roundRect(PANEL.x,PANEL.y,PANEL.w,PANEL.h,16);ctx.fill();
 ctx.strokeStyle=COL.grid;ctx.lineWidth=1.5;for(let g=0;g<=5;g++){const y=PLOT.y+g*PLOT.h/5;ctx.beginPath();ctx.moveTo(PLOT.x,y);ctx.lineTo(PLOT.x+PLOT.w,y);ctx.stroke()}
 ctx.font=`500 18px ${FONT}`;ctx.fillStyle='#5d6e8a';ctx.textAlign='left';ctx.fillText(ch.symbol,PANEL.x+24,PANEL.y+PANEL.h-18);
 // annotations that sit behind candles: zones, boxes, hlines
 const RL=[];const on=ch.ann.filter(a=>annOn(a,s,v));
 const boxes={};on.filter(a=>a.type==='box').forEach(a=>{if(!boxes[a.id]||boxes[a.id].scene<=a.scene)boxes[a.id]=a});
 on.filter(a=>a.type==='zone').forEach(a=>{const al=annAlpha(a,s,v,t),x0=xOf(ch,a.idx||0)-3,x1=a.to!==undefined?xOf(ch,a.to):PLOT.x+PLOT.w,y1=yOf(ch,a.p2),y2=yOf(ch,a.p1);ctx.save();ctx.globalAlpha=al;ctx.fillStyle=a.color+'26';ctx.fillRect(x0,y1,x1-x0,y2-y1);ctx.strokeStyle=a.color;ctx.lineWidth=1.5;ctx.setLineDash([8,7]);ctx.beginPath();ctx.moveTo(x0,y1);ctx.lineTo(x1,y1);ctx.moveTo(x0,y2);ctx.lineTo(x1,y2);ctx.stroke();ctx.setLineDash([]);
  if(a.to===undefined||x1>=PLOT.x+PLOT.w-2){RL.push({y:(y1+y2)/2+6,c:a.color,l:a.label,p:null,al:al})}ctx.restore()});
 Object.values(boxes).forEach(a=>{const al=annAlpha(a,s,v,t),x0=xOf(ch,a.idx),x1=PLOT.x+PLOT.w,yE=yOf(ch,a.entry),yS=yOf(ch,a.stop),yT=yOf(ch,a.target),da=a.dashed?.55:1;ctx.save();ctx.globalAlpha=al*da;
  ctx.fillStyle='rgba(45,179,166,.15)';ctx.fillRect(x0,Math.min(yE,yT),x1-x0,Math.abs(yT-yE));ctx.fillStyle='rgba(226,65,99,.20)';ctx.fillRect(x0,Math.min(yE,yS),x1-x0,Math.abs(yS-yE));
  const ln=(y,c,lab,pr)=>{ctx.strokeStyle=c;ctx.lineWidth=2;ctx.setLineDash([9,7]);ctx.beginPath();ctx.moveTo(x0,y);ctx.lineTo(x1,y);ctx.stroke();ctx.setLineDash([]);RL.push({y:y-6,c:c,l:lab,p:pr,al:al*da})};
  ln(yE,COL.gold,'ENTRY',a.entry);ln(yS,COL.dn,'STOP LOSS',a.stop);ln(yT,COL.up,'TARGET',a.target);
  if(a.rr&&s.k>=a.rrscene){pill(ctx,a.rr,(x0+x1)/2,(yE+yT)/2,COL.up,1)}ctx.restore()});
 on.filter(a=>a.type==='hline').forEach(a=>{const al=annAlpha(a,s,v,t),x0=xOf(ch,a.idx||0),x1=a.to!==undefined?xOf(ch,a.to):PLOT.x+PLOT.w,y=yOf(ch,a.price);ctx.save();ctx.globalAlpha=al;ctx.strokeStyle=a.color;ctx.lineWidth=2.2;ctx.setLineDash([10,8]);ctx.beginPath();ctx.moveTo(x0,y);ctx.lineTo(x1,y);ctx.stroke();ctx.setLineDash([]);
  if(a.label&&(a.to===undefined||x1>=PLOT.x+PLOT.w-2)){RL.push({y:y-6,c:a.color,l:a.label,p:a.price,al:al})}ctx.restore()});
 // candles
 const n=ch.candles.length,slot=PLOT.w/n,bw=Math.max(4,slot*.62);const full=Math.floor(v),frac=v-full;
 for(let k=0;k<Math.min(n,full+1);k++){let[o,h,l,c]=ch.candles[k];if(k===full){if(frac<=0)break;c=o+(c-o)*frac;h=Math.max(o,c)+(h-Math.max(ch.candles[k][0],ch.candles[k][3]))*frac;l=Math.min(o,c)-(Math.min(ch.candles[k][0],ch.candles[k][3])-l)*frac}
  const x=xOf(ch,k),up=c>=o,col=up?COL.up:COL.dn;ctx.strokeStyle=col;ctx.lineWidth=2.2;ctx.beginPath();ctx.moveTo(x,yOf(ch,h));ctx.lineTo(x,yOf(ch,l));ctx.stroke();const y1=yOf(ch,Math.max(o,c)),y2=yOf(ch,Math.min(o,c));ctx.fillStyle=col;ctx.fillRect(x-bw/2,y1,bw,Math.max(2,y2-y1))}
 // annotations on top
 on.filter(a=>['circle','arrow','tag'].includes(a.type)).forEach(a=>{const al=annAlpha(a,s,v,t),x=xOf(ch,a.idx),y=yOf(ch,a.price);
  if(a.type==='circle'){ctx.save();ctx.globalAlpha=al;ctx.strokeStyle=a.color;ctx.lineWidth=3.2;ctx.beginPath();ctx.arc(x,y,17,0,7);ctx.stroke();ctx.restore()}
  else if(a.type==='arrow'){ctx.save();ctx.globalAlpha=al;ctx.fillStyle=a.color;ctx.strokeStyle=a.color;ctx.lineWidth=4;const d=a.dir==='down'?1:-1,y0=y-d*62,y1=y-d*10;ctx.beginPath();ctx.moveTo(x,y0);ctx.lineTo(x,y1-d*8);ctx.stroke();ctx.beginPath();ctx.moveTo(x,y1);ctx.lineTo(x-10,y1-d*18);ctx.lineTo(x+10,y1-d*18);ctx.closePath();ctx.fill();ctx.restore();if(a.text)pill(ctx,a.text,x,y0-d*26,a.color,al)}
  else if(a.type==='tag'){pill(ctx,a.text,x,y+(a.dy||0),a.color,al)}});
 // right-margin labels with spacing
 RL.sort((a,b)=>a.y-b.y);let lastY=-999,lastH=0;RL.forEach(r=>{const h=r.p!==null?46:28;let y=r.y;if(y<lastY+lastH)y=lastY+lastH;r.y2=y;lastY=y;lastH=h;ctx.save();ctx.globalAlpha=r.al;ctx.font=`800 18px ${FONT}`;ctx.textAlign='left';ctx.fillStyle=r.c;ctx.fillText(r.l,PLOT.x+PLOT.w+14,y);if(r.p!==null){ctx.fillStyle=COL.white;ctx.fillText(Math.round(r.p).toLocaleString('en-US'),PLOT.x+PLOT.w+14,y+22)}ctx.restore()});
 // footer
 ctx.font=`500 20px ${FONT}`;ctx.fillStyle='#6a7b97';ctx.textAlign='left';ctx.fillText('Illustrative example  ·  not a real trade  ·  not financial advice',80,1052);ctx.textAlign='right';ctx.fillText('gopipways.com',1840,1052)}
function paint(ctx,i,t){if(SC[i].type==='F')paintFigure(ctx,i,t);else paintChart(ctx,i,t)}
function caption(t){let k=-1;for(let i=0;i<CAP.length;i++){if(t>=CAP[i][0]-.02)k=i;else break}if(k<0)return;const c=CAP[k];if(t>c[1]+.15)return;const i=sceneAt(t),isF=SC[i].type==='F';
 const x=MAIN;x.save();x.font=`800 ${isF?46:42}px ${FONT}`;x.textAlign='center';x.lineJoin='round';const words=c[2].split(' '),maxW=1560;let ls=[],cur='';for(const w of words){const tt=cur?cur+' '+w:w;if(x.measureText(tt).width>maxW){ls.push(cur);cur=w}else cur=tt}ls.push(cur);x.globalAlpha=clamp((t-c[0])/.12);
 const base=isF?1024:1000;ls.forEach((ln,j)=>{const y=base-(ls.length-1-j)*56;x.lineWidth=12;x.strokeStyle='rgba(0,0,0,.92)';x.strokeText(ln,CW/2,y);x.fillStyle='#fff';x.fillText(ln,CW/2,y)});x.restore()}
const OFF1=document.createElement('canvas'),OFF2=document.createElement('canvas');OFF1.width=OFF2.width=CW;OFF1.height=OFF2.height=CH;const TR=.3;
function draw(t){const i=sceneAt(t),s=SC[i],u=t-s.a;const pv=i>0?SC[i-1]:null;const same=pv&&pv.type==='C'&&s.type==='C'&&SCH[pv.k]===SCH[s.k];
 if(i>0&&u<TR&&!same){const p=ease(u/TR);paint(OFF1.getContext('2d'),i-1,SC[i-1].b-.001);paint(OFF2.getContext('2d'),i,t);MAIN.clearRect(0,0,CW,CH);MAIN.drawImage(OFF1,0,0);MAIN.globalAlpha=p;MAIN.drawImage(OFF2,0,0);MAIN.globalAlpha=1}else paint(MAIN,i,t);
 caption(t);MAIN.fillStyle='#16233a';MAIN.fillRect(0,CH-8,CW,8);MAIN.fillStyle=COL.up;MAIN.fillRect(0,CH-8,CW*clamp(t/DURATION),8)}
window.draw=draw;
