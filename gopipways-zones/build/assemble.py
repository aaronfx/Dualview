import json,re,sys,os,numpy as np,difflib
sys.path.insert(0,'/home/user/Dualview/gopipways-zones');sys.path.insert(0,'.')
from spec import S as SPEC
import charts
G='/tmp/claude-0/gz';D=1070.76
P=[l.strip() for l in open('/home/user/Dualview/gopipways-zones/script_new.txt') if l.strip()]
# word-level times
ws=[(re.sub(r'\(\d+\)','',w),a,b) for w,a,b in json.load(open(G+'/words.json')) if w not in('<sil>','[SPEECH]','<s>','</s>','[NOISE]')]
tw=[];own=[]
for i,l in enumerate(P):
    for w in re.findall(r"[a-z0-9']+",l.lower().replace('’',"'")):tw.append(w);own.append(i)
m=difflib.SequenceMatcher(None,tw,[w for w,_,_ in ws],autojunk=False)
t=[None]*len(tw)
for a,b,n in m.get_matching_blocks():
    for k in range(n):t[a+k]=ws[b+k][1]
idx=[i for i,v in enumerate(t) if v is not None];t=list(np.interp(range(len(t)),idx,[t[i] for i in idx]))
pw={};
for k,o in enumerate(own):pw.setdefault(o,[]).append(t[k])
st=[pw[i][0] for i in range(len(P))];st[0]=0.0
SC=[]
for i in range(len(P)):
    k=i+1;a=st[i];b=st[i+1] if i+1<len(P) else D
    ty=SPEC[k][0]
    d=dict(k=k,a=round(a,2),b=round(b,2),type=ty)
    if ty=='F':d['label']={4:'MARKING ZONES',5:'YOU ASKED FOR THIS'}.get(k,SPEC[k][1])
    SC.append(d)
SCH={str(k):cid for k,cid in charts.SCENE2CH.items()}
# captions
CAP=[]
for i,para in enumerate(P):
    sents=re.split(r'(?<=[.?!”"])\s+',para);wi=0;ts=pw[i];pend=(st[i+1] if i+1<len(P) else D)
    items=[]
    for s in sents:
        words=s.split()
        if not words:continue
        nch=max(1,-(-len(words)//12));size=-(-len(words)//nch)
        for c0 in range(0,len(words),size):
            ch=words[c0:c0+size];wt=ts[min(len(ts)-1,wi+c0)] if wi+c0<len(ts) else ts[-1]
            items.append([wt,' '.join(ch)])
        wi+=len(words)
    for j,(a,tx) in enumerate(items):
        e=items[j+1][0] if j+1<len(items) else pend
        CAP.append([round(a,2),round(max(a+.4,e-.05),2),tx])
# ---- shots: phrase-synced cuts so the picture changes every ~3-5 s
TEASER={'A':dict(chart='A',beat=8,title='SPOT THE LEVEL',sub='Where price gets rejected again and again.',chip='PREVIEW / WHAT YOU WILL LEARN'),
 'H':dict(chart='H',beat=51,title='STRENGTH + STRUCTURE',sub='The two questions that filter the best zones.',chip='PREVIEW / WHAT YOU WILL LEARN'),
 'F':dict(chart='F',beat=17,title='WHEN A LEVEL FLIPS',sub='Resistance becomes support, and the reverse.',chip='PREVIEW / ADVANCED CONCEPTS'),
 'B':dict(chart='B',beat=9,title='FIND SUPPORT',sub='Where buyers step in.',chip='PREVIEW / REVISION')}
PLAN={1:[('F',0,'COMPLETE BEGINNER?'),('F',1,'2-3 YEARS IN?'),('T','A',None),('F',3,'WATCH TILL THE END'),('T','H',None)],
 2:[('F',2,'EVERYTHING EXPLAINED'),('T','F',None),('F',5,'EVEN ON THE 1-MINUTE CHART')],
 3:[('F',6,'ONE OR TWO YEARS IN?'),('F',4,'WATCH IT ALL'),('T','B',None),('F',1,"DON'T SKIP AHEAD"),('F',3,'LEARN SOMETHING NEW')]}
def chunks_of(s):return [c[0] for c in CAP if s['a']-0.01<=c[0]<s['b']-0.05]
nshots=0
for s in SC:
    if s['type']!='F':continue
    cs=chunks_of(s);d=s['b']-s['a']
    if s['k'] in PLAN:
        plan=PLAN[s['k']];starts=[s['a']]+[cs[j] for j in range(1,len(plan))]
        sh=[]
        for j,(kind,x,lab) in enumerate(plan):
            a=starts[j];b=starts[j+1] if j+1<len(starts) else s['b']
            if kind=='F':sh.append(dict(a=round(a,2),b=round(b,2),k='F',f=x,lab=lab))
            else:
                sh.append(dict(a=round(a,2),b=round(b,2),k='T',**TEASER[x]))
        s['shots']=sh
    elif d>6.5:
        starts=[s['a']];
        for c in cs[1:]:
            if c-starts[-1]>=3.0 and s['b']-c>=2.0:starts.append(c)
        # split any remaining long gap in equal parts (max ~5 s)
        ends=starts[1:]+[s['b']];st2=[]
        for a0,b0 in zip(starts,ends):
            n=max(1,round((b0-a0)/4.6)) if b0-a0>5.6 else 1
            st2+= [a0+(b0-a0)*q/n for q in range(n)]
        starts=st2
        f=(s['k']*3)%7;sh=[]
        for j,a in enumerate(starts):
            b=starts[j+1] if j+1<len(starts) else s['b']
            sh.append(dict(a=round(a,2),b=round(b,2),k='F',f=f));f=(f+2+j)%7
        s['shots']=sh
    nshots+=len(s.get('shots',[]))
gaps=[round(sh['b']-sh['a'],1) for s in SC if s['type']=='F' for sh in (s.get('shots') or [dict(a=s['a'],b=s['b'])])]
print('figure shots',nshots,'longest figure shot',max(gaps),'s')
CHARTS={cid:{k:v for k,v in c.items() if k!='markers'} for cid,c in charts.S.items()}
os.makedirs('site',exist_ok=True)
if not os.path.exists('site/imgs'):os.symlink(G+'/imgs/Scene_Images','site/imgs')
js=open('engine.js').read()
tpl='<!doctype html><html><head><meta charset="utf-8"><title>Zones</title><style>html,body{margin:0;background:#111}canvas{display:block;width:100%;max-width:960px;height:auto}</style></head><body><canvas id="c"></canvas><script>const DURATION=@D;const SC=@SC;const SCH=@SCH;const CAP=@CAP;const CHARTS=@CH;\n@JS</script></body></html>'
html=tpl.replace('@D',str(D)).replace('@SCH',json.dumps(SCH)).replace('@SC',json.dumps(SC)).replace('@CAP',json.dumps(CAP,ensure_ascii=False)).replace('@CH',json.dumps(CHARTS)).replace('@JS',js)
open('site/index.html','w').write(html)
print(len(SC),len(CAP),'scenes; html',len(html)//1024,'KB')
