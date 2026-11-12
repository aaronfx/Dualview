// usage: node render.js <outDir> [fps] [t1,t2,...]
const { chromium } = require('playwright'); const fs=require('fs'), path=require('path');
(async()=>{
  const out=process.argv[2], fps=+(process.argv[3]||24), only=process.argv[4]?process.argv[4].split(',').map(Number):null;
  const b=await chromium.launch(); const p=await b.newPage({viewport:{width:1280,height:720}});
  p.on('pageerror',e=>console.error('ERR',e.message));
  await p.goto('file://'+path.resolve(__dirname,'index.html')+'#render');
  const times=only||Array.from({length:Math.floor(49.63*fps)},(_,i)=>i/fps);
  for(let i=0;i<times.length;i++){
    const d=await p.evaluate(t=>{draw(t);return document.getElementById('c').toDataURL('image/jpeg',0.92).split(',')[1]},times[i]);
    fs.writeFileSync(path.join(out,only?`t${times[i]}.jpg`:`f${String(i).padStart(5,'0')}.jpg`),Buffer.from(d,'base64'));
  }
  await b.close();
})();
