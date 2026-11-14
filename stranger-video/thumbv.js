// usage: node thumbv.js <outDir>  -> thumbv_A/B/C.png (1080x1920, vertical)
const { chromium } = require('playwright'); const fs=require('fs'), path=require('path');
(async()=>{
  const out=process.argv[2]; fs.mkdirSync(out,{recursive:true});
  const b=await chromium.launch(); const p=await b.newPage({viewport:{width:1280,height:720}});
  p.on('pageerror',e=>console.error('ERR',e.message));
  await p.goto('file://'+path.resolve(__dirname,'lastloaf.html')+'#render');
  for(const k of ['A','B','C']){
    const d=await p.evaluate(k=>{drawThumbV(k);return document.getElementById('c').toDataURL('image/png').split(',')[1]},k);
    fs.writeFileSync(path.join(out,`thumbv_${k}.png`),Buffer.from(d,'base64'));
  }
  await b.close();
})();
