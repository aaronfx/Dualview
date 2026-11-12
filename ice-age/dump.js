const { chromium } = require('playwright');const path=require('path');const fs=require('fs');
(async()=>{const b=await chromium.launch();const p=await b.newPage();await p.goto('file://'+path.resolve('ice.html')+'#render&landscape');
const r=await p.evaluate(()=>SC.map((s,i)=>{const a=s[0],e=s[1];const txt=[];for(let k=0;k<S.length;k++){const st=S[k],en=k+1<S.length?S[k+1]:428.2;if(en>a+.05&&st<e-.05)txt.push(SENTS[k])}return {i,a:+a.toFixed(2),e:+e.toFixed(2),text:txt.join(' ')}}));
fs.writeFileSync('/tmp/claude-0/ice/scenes.json',JSON.stringify(r));
console.log(r.map(x=>`${x.i}|${x.a}-${x.e}|${x.text}`).join('\n'));await b.close()})();
