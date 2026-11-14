const { chromium } = require('playwright');const path=require('path');
(async()=>{const b=await chromium.launch();const p=await b.newPage();await p.goto('file://'+path.resolve('ice.html')+'#render&landscape');
const r=await p.evaluate(()=>SC.map((s,i)=>[i,+s[0].toFixed(2),+(s[1]-s[0]).toFixed(2)]));
const long=r.filter(x=>x[2]>5);console.log('scenes',r.length,'max',Math.max(...r.map(x=>x[2])));console.log(JSON.stringify(long));await b.close()})();
