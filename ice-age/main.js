// ---- rendering with transitions + captions ----
SC.sort((a,b)=>a[0]-b[0]);SC[0][0]=0;for(let i=0;i<SC.length-1;i++)SC[i][1]=SC[i+1][0];SC[SC.length-1][1]=428.2;
const TR=0.35,OFF1=document.createElement('canvas'),OFF2=document.createElement('canvas');OFF1.width=OFF2.width=CW;OFF1.height=OFF2.height=CH;
function paint(ctx,i,t){
  const sc=SC[i];const u=t-sc[0],dur=Math.max(.5,sc[1]-sc[0]);c=ctx;
  c.clearRect(0,0,CW,CH);c.fillStyle=sc[2];c.fillRect(0,0,CW,CH);
  c.save();c.scale(K,K);c.translate(W/2,H/2);const z=1+.05*(u/dur);c.scale(z,z);c.translate(-W/2,-H/2);FS=2.25;
  if(sc[4]){const zz=lerp(1,sc[4][0],ease(u/.5));c.translate(sc[4][1],sc[4][2]);c.scale(zz,zz);c.translate(-sc[4][1],-sc[4][2])}
  sc[3](Math.max(0,u),t);c.restore();c=MAIN}
function caption(t){
  let k=-1;for(let i=0;i<S.length;i++){if(t>=S[i]-0.02)k=i;else break}
  if(k<0)return;const s=SENTS[k];const end=(k+1<S.length?S[k+1]:428.2);if(t>end-0.0)return;
  const x=MAIN;x.save();x.font='800 40px "Trebuchet MS","DejaVu Sans",Arial,sans-serif';x.textAlign='center';x.lineJoin='round';
  const words=s.split(' '),maxW=1650;let lines=[],cur='';for(const w of words){const tt=cur?cur+' '+w:w;if(x.measureText(tt).width>maxW){lines.push(cur);cur=w}else cur=tt}lines.push(cur);
  const a=clamp((t-S[k])/0.12);x.globalAlpha=a;
  lines.forEach((ln,j)=>{const y=CH-40-(lines.length-1-j)*52;x.lineWidth=11;x.strokeStyle='rgba(0,0,0,.92)';x.strokeText(ln,CW/2,y);x.fillStyle='#fff';x.fillText(ln,CW/2,y)});x.restore()}
function draw(t){
  let i=SC.findIndex(s=>t>=s[0]&&t<s[1]);if(i<0)i=SC.length-1;const u=t-SC[i][0];
  if(i>0&&u<TR){const p=ease(u/TR),kind=i%4;paint(OFF1.getContext('2d'),i-1,SC[i-1][1]-0.001);paint(OFF2.getContext('2d'),i,t);MAIN.clearRect(0,0,CW,CH);
    if(kind===0){MAIN.drawImage(OFF1,-p*CW,0);MAIN.drawImage(OFF2,CW-p*CW,0)}
    else if(kind===1){MAIN.drawImage(OFF1,0,0);MAIN.save();MAIN.beginPath();MAIN.arc(CW/2,CH/2,p*Math.hypot(CW,CH)/2,0,7);MAIN.clip();MAIN.drawImage(OFF2,0,0);MAIN.restore()}
    else if(kind===2){MAIN.drawImage(OFF1,0,p*CH);MAIN.drawImage(OFF2,0,p*CH-CH)}
    else{MAIN.drawImage(OFF1,0,0);MAIN.globalAlpha=p;MAIN.drawImage(OFF2,0,0);MAIN.globalAlpha=1}
  }else paint(MAIN,i,t);
  caption(t)}
window.draw=draw;window.DURATION=428.2;
if(!location.hash.includes('render')){const t0=performance.now();(function loop(){draw(((performance.now()-t0)/1000)%428.2);requestAnimationFrame(loop)})()}
