// usage: PAGE=ice.html node render2.js <outDir> <fps> <shard> <nshards>
const { chromium } = require('playwright'); const fs=require('fs'), path=require('path');
(async()=>{
  const out=process.argv[2], fps=+process.argv[3], k=+process.argv[4], n=+process.argv[5];
  const b=await chromium.launch(); const p=await b.newPage({viewport:{width:1280,height:720}});
  p.on('pageerror',e=>console.error('ERR',e.message));
  await p.goto('file://'+path.resolve(__dirname,process.env.PAGE||'ice.html')+'#render&landscape');
  const DUR=await p.evaluate(()=>window.DURATION); const N=Math.floor(DUR*fps);
  for(let i=k;i<N;i+=n){
    const d=await p.evaluate(t=>{draw(t);return document.getElementById('c').toDataURL('image/jpeg',0.9).split(',')[1]},i/fps);
    fs.writeFileSync(path.join(out,`f${String(i).padStart(5,'0')}.jpg`),Buffer.from(d,'base64'));
  }
  await b.close(); console.log('shard',k,'done');
})();
