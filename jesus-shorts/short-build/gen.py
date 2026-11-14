import json,re
T=json.load(open('timing.json'));st=T['starts'];lines=T['lines'];DUR=51.15
SCN=[[st[i],(st[i+1] if i+1<len(st) else DUR)] for i in range(len(st))]
lab=[]
src=open('/home/user/Dualview/jesus-shorts/data.py').read()
import importlib.util,sys
sys.path.insert(0,'/home/user/Dualview/jesus-shorts')
import data
labels=[x[1] for x in data.S[0]['scenes']]
js=r'''
const CW=1080,CH=1920,cv=document.getElementById('c');cv.width=CW;cv.height=CH;const MAIN=cv.getContext('2d');
const clamp=(x,a=0,b=1)=>Math.min(b,Math.max(a,x)),lerp=(a,b,t)=>a+(b-a)*t,ease=t=>{t=clamp(t);return t<.5?2*t*t:1-Math.pow(-2*t+2,2)/2};
const N=SCN.length,IM=[];let loaded=0;
window.READY=new Promise(res=>{for(let i=0;i<N;i++){const im=new Image();im.onload=im.onerror=()=>{if(++loaded===N)res(true)};im.src='imgs/short1_'+String(i+1).padStart(3,'0')+'.jpg';IM.push(im)}});
const FONT='"Trebuchet MS","DejaVu Sans",Arial,sans-serif';
function kb(i,u,dur){const p=clamp(u/dur);let z,ax=.5,ay=.5;const m=i%6;const Z=.11;
 if(m===0){z=1+Z*p}else if(m===1){z=1+Z*(1-p)}else if(m===2){z=1+Z;ax=lerp(.15,.85,p)}else if(m===3){z=1+Z;ax=lerp(.85,.15,p)}else if(m===4){z=1+Z*p;ay=.3}else{z=1+Z;ay=lerp(.2,.8,p)}
 const iw=IM[i].naturalWidth||720,ih=IM[i].naturalHeight||1280;const base=Math.max(CW/iw,CH/ih);const w=iw*base*z,h=ih*base*z;return[-(w-CW)*ax,-(h-CH)*ay,w,h]}
function snow(ctx,t,n){ctx.fillStyle='rgba(255,255,255,.8)';for(let k=0;k<n;k++){const x=((k*97.3+t*(22+(k%5)*7))%1250)-80,y=((k*53.1+t*(80+(k%7)*14))%2050)-80;ctx.beginPath();ctx.arc(x,y,2+(k%3)*1.2,0,7);ctx.fill()}}
function outlined(ctx,s,x,y,fs,fill,stroke,lw){ctx.font=`800 ${fs}px ${FONT}`;ctx.textAlign='center';ctx.lineJoin='round';ctx.lineWidth=lw;ctx.strokeStyle=stroke;ctx.strokeText(s,x,y);ctx.fillStyle=fill;ctx.fillText(s,x,y)}
function paint(ctx,i,t){const sc=SCN[i],u=t-sc[0],dur=Math.max(.6,sc[1]-sc[0]);ctx.clearRect(0,0,CW,CH);const r=kb(i,u,dur);ctx.drawImage(IM[i],r[0],r[1],r[2],r[3]);
 if(i<=12)snow(ctx,t,60);
 const g=ctx.createRadialGradient(CW/2,CH/2,CH*.4,CW/2,CH/2,CH*.85);g.addColorStop(0,'rgba(0,0,0,0)');g.addColorStop(1,'rgba(0,0,0,.30)');ctx.fillStyle=g;ctx.fillRect(0,0,CW,CH);
 // top shade for label legibility
 const tg=ctx.createLinearGradient(0,0,0,420);tg.addColorStop(0,'rgba(0,0,0,.45)');tg.addColorStop(1,'rgba(0,0,0,0)');ctx.fillStyle=tg;ctx.fillRect(0,0,CW,420);
 if(t>HOOK_END){const l=(i===N-1)?null:LABELS[i];if(l){const a=Math.min(1,clamp(u/.2)*clamp((dur-u)/.15+.4));ctx.save();ctx.globalAlpha=a;let fs=78;ctx.font=`800 ${fs}px ${FONT}`;while(ctx.measureText(l).width>CW-170&&fs>40){fs-=4;ctx.font=`800 ${fs}px ${FONT}`}
   const y=300+(1-ease(u/.25))*-24;outlined(ctx,l,CW/2-20,y,fs,'#ffe14d','#000',16);ctx.restore()}}}
const HOOK_END=3.6,HOOK=['WOULD YOU HAVE','HELPED HIM?'];
function hook(t){if(t>HOOK_END)return;const a=clamp(t/.2)*clamp((HOOK_END-t)/.25);const pop=1+.06*Math.sin(clamp(t/.35)*Math.PI);MAIN.save();MAIN.globalAlpha=a;MAIN.translate(CW/2-20,330);MAIN.scale(pop,pop);outlined(MAIN,HOOK[0],0,0,84,'#ffe14d','#000',18);outlined(MAIN,HOOK[1],0,110,112,'#ffe14d','#000',22);MAIN.restore()}
const OFF1=document.createElement('canvas'),OFF2=document.createElement('canvas');OFF1.width=OFF2.width=CW;OFF1.height=OFF2.height=CH;const TR=.22;
function caption(t){let k=-1;for(let i=0;i<N;i++){if(t>=SCN[i][0]-.02)k=i;else break}if(k<0)return;if(t>SCN[k][1])return;const x=MAIN;x.save();x.font=`800 58px ${FONT}`;x.textAlign='center';x.lineJoin='round';
 const words=LINES[k].split(' '),maxW=CW-200;let ls=[],cur='';for(const w of words){const tt=cur?cur+' '+w:w;if(x.measureText(tt).width>maxW){ls.push(cur);cur=w}else cur=tt}ls.push(cur);x.globalAlpha=clamp((t-SCN[k][0])/.1);
 ls.forEach((ln,j)=>{const y=1440-(ls.length-1-j)*74;x.lineWidth=14;x.strokeStyle='rgba(0,0,0,.92)';x.strokeText(ln,CW/2-20,y);x.fillStyle='#fff';x.fillText(ln,CW/2-20,y)});x.restore()}
function draw(t){let i=SCN.findIndex(s=>t>=s[0]&&t<s[1]);if(i<0)i=N-1;const u=t-SCN[i][0];
 if(i>0&&u<TR){const p=ease(u/TR);paint(OFF1.getContext('2d'),i-1,SCN[i-1][1]-.001);paint(OFF2.getContext('2d'),i,t);MAIN.clearRect(0,0,CW,CH);MAIN.drawImage(OFF1,0,0);MAIN.globalAlpha=p;MAIN.drawImage(OFF2,0,0);MAIN.globalAlpha=1}else paint(MAIN,i,t);
 hook(t);caption(t);
 if(i===N-1){const a=ease(u/.5);MAIN.save();MAIN.globalAlpha=a;outlined(MAIN,'AMEN',CW/2-20,1150,150,'#ffe14d','#000',24);MAIN.restore()}}
window.draw=draw;window.DURATION=__DUR__;
'''.replace('__DUR__',str(DUR))
labs={i:l for i,l in enumerate(labels)}
head='const SCN=%s;const LINES=%s;const LABELS=%s;'%(json.dumps(SCN),json.dumps(lines),json.dumps(labs))
html='<!doctype html><html><head><meta charset="utf-8"><title>Short1</title><style>html,body{margin:0;background:#111}canvas{display:block;width:100%;max-width:540px;height:auto}</style></head><body><canvas id="c"></canvas><script>'+head+js+'</script></body></html>'
open('site/short.html','w').write(html);print(len(SCN),DUR)
