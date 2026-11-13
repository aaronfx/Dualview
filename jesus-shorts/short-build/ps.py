import json,wave
from pocketsphinx import Decoder
d=Decoder(samprate=16000,logfn='/dev/null')
w=wave.open('n16.wav','rb')
d.start_utt()
while True:
    b=w.readframes(4000)
    if not b: break
    d.process_raw(b,False,False)
d.end_utt()
out=[(s.word,round(s.start_frame/100,2),round(s.end_frame/100,2)) for s in d.seg()]
json.dump(out,open('words.json','w'))
print(len(out)); print(' '.join(f"{a}@{b}" for a,b,_ in out[:50]))
