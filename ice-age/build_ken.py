import json,os,shutil
sc=json.load(open('/tmp/claude-0/ice/scenes.json'))
SCN=[[s['a'],s['e']] for s in sc];SCN[0][0]=0;SCN[-1][1]=428.2
for i in range(len(SCN)-1):SCN[i][1]=SCN[i+1][0]
site='/tmp/claude-0/ice/site';os.makedirs(site,exist_ok=True)
link=site+'/imgs'
if not os.path.exists(link):os.symlink('/tmp/claude-0/ice/imgs_user/Ice_Age_JPG',link)
parts=['const SCN='+json.dumps(SCN)+';',open('timings.js').read(),open('sents.js').read(),open('ken_main.js').read()]
html='<!doctype html><html><head><meta charset="utf-8"><title>Ice Age Ken Burns</title><style>html,body{margin:0;background:#111}canvas{display:block;width:100%;max-width:960px;height:auto}</style></head><body><canvas id="c"></canvas><script>'+'\n'.join(parts)+'</script></body></html>'
open(site+'/ken.html','w').write(html);open('ken.html','w').write(html)
print(len(SCN))
