// node render_seg.js <outDir> <fps> <t0> <t1>
const { chromium } = require('playwright'); const fs=require('fs'), path=require('path');
(async()=>{
  const out=process.argv[2], fps=+process.argv[3], t0=+process.argv[4], t1=+process.argv[5];
  const b=await chromium.launch(); const p=await b.newPage({viewport:{width:1920,height:1080}});
  p.on('pageerror',e=>console.error('ERR',e.message));
  await p.goto('http://localhost:8768/index.html#render'); await p.evaluate(()=>window.READY);
  const n0=Math.round(t0*fps), n1=Math.min(Math.round(t1*fps), Math.floor((await p.evaluate(()=>DURATION))*fps));
  for(let i=n0;i<n1;i++){const d=await p.evaluate(t=>{draw(t);return document.getElementById('c').toDataURL('image/jpeg',0.9).split(',')[1]},i/fps);fs.writeFileSync(path.join(out,`f${String(i-n0).padStart(5,'0')}.jpg`),Buffer.from(d,'base64'))}
  await b.close();console.log('seg done',t0,t1);
})();
