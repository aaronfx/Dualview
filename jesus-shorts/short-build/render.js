// usage: node render3.js <outDir> <fps> <shard> <nshards> [t1,t2,...]   (page served at http://localhost:8766/short.html)
const { chromium } = require('playwright'); const fs=require('fs'), path=require('path');
(async()=>{
  const out=process.argv[2], fps=+process.argv[3], k=+process.argv[4], n=+process.argv[5], only=process.argv[6]?process.argv[6].split(',').map(Number):null;
  const b=await chromium.launch(); const p=await b.newPage({viewport:{width:1080,height:1920}});
  p.on('pageerror',e=>console.error('ERR',e.message));
  await p.goto('http://localhost:8766/short.html#render'); await p.evaluate(()=>window.READY);
  if(only){for(const t of only){const d=await p.evaluate(t=>{draw(t);return document.getElementById('c').toDataURL('image/jpeg',0.92).split(',')[1]},t);fs.writeFileSync(path.join(out,`t${t}.jpg`),Buffer.from(d,'base64'))}await b.close();return}
  const DUR=await p.evaluate(()=>window.DURATION),N=Math.floor(DUR*fps);
  for(let i=k;i<N;i+=n){const d=await p.evaluate(t=>{draw(t);return document.getElementById('c').toDataURL('image/jpeg',0.92).split(',')[1]},i/fps);fs.writeFileSync(path.join(out,`f${String(i).padStart(5,'0')}.jpg`),Buffer.from(d,'base64'))}
  await b.close();console.log('shard',k,'done');
})();
