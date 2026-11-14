const { chromium } = require('playwright');const fs=require('fs'),path=require('path');
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1280,height:720}});p.on('pageerror',e=>console.error('ERR',e.message));
await p.goto('file://'+path.resolve('ice.html')+'#render&landscape');
const mids=await p.evaluate(()=>SC.map(s=>[(s[0]+Math.min(s[1],s[0]+4))/2+0.5,s[0],s[1]]));
fs.writeFileSync('/tmp/claude-0/ice/mids.json',JSON.stringify(mids));
const out='/tmp/claude-0/ice/mid';fs.mkdirSync(out,{recursive:true});
for(let i=0;i<mids.length;i++){const t=Math.min(mids[i][0],mids[i][2]-.05);
 const d=await p.evaluate(t=>{draw(t);return document.getElementById('c').toDataURL('image/jpeg',0.85).split(',')[1]},t);
 fs.writeFileSync(path.join(out,`m${String(i).padStart(3,'0')}.jpg`),Buffer.from(d,'base64'));}
console.log(mids.length);await b.close()})();
