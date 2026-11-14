// usage: node thumb.js <outDir>   -> writes thumb_A.png, thumb_B.png, thumb_C.png (1280x720)
const { chromium } = require('playwright'); const fs=require('fs'), path=require('path');
(async()=>{
  const out=process.argv[2]; fs.mkdirSync(out,{recursive:true});
  const b=await chromium.launch(); const p=await b.newPage({viewport:{width:1280,height:720}});
  p.on('pageerror',e=>console.error('ERR',e.message));
  await p.goto('file://'+path.resolve(__dirname,'lastloaf.html')+'#render&landscape');
  for(const k of ['A','B','C']){
    const d=await p.evaluate(k=>{drawThumb(k);return document.getElementById('c').toDataURL('image/png').split(',')[1]},k);
    fs.writeFileSync(path.join(out,`thumb_${k}.png`),Buffer.from(d,'base64'));
  }
  await b.close();
})();
