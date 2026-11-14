import json,re,difflib,numpy as np
lines=[l.strip() for l in open('/home/user/Dualview/jesus-shorts/pack/short1/narration_for_elevenlabs.txt').read().split('\n\n') if l.strip()]
ws=[(re.sub(r'\(\d+\)','',w),a,b) for w,a,b in json.load(open('words.json')) if w not in('<sil>','[SPEECH]','<s>','</s>','[NOISE]')]
tw=[];own=[]
for i,l in enumerate(lines):
    for w in re.findall(r"[a-z']+",l.lower()): tw.append(w);own.append(i)
m=difflib.SequenceMatcher(None,tw,[w for w,_,_ in ws],autojunk=False)
t=[None]*len(tw)
for a,b,n in m.get_matching_blocks():
    for k in range(n): t[a+k]=ws[b+k][1]
idx=[i for i,v in enumerate(t) if v is not None]
t=list(np.interp(range(len(t)),idx,[t[i] for i in idx]))
st=[None]*len(lines)
for k,o in enumerate(own):
    if st[o] is None: st[o]=round(float(t[k]),2)
st[0]=0.0
json.dump({'starts':st,'lines':lines},open('timing.json','w'))
print(len(lines),len(idx)/len(tw));print(st)
