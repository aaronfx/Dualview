import csv,os,shutil,zipfile,re
from spec import S
P=[l.strip() for l in open('script_full.txt').read().split('\n') if l.strip()]
assert len(P)==len(S)==115
out='pack'; shutil.rmtree(out,ignore_errors=True); os.makedirs(out+'/chatgpt-batches')
MASTER="""# STEP 1 - paste this ONCE at the start of a new ChatGPT chat

You are my image generator for a trading-education YouTube video. I will send numbered batches of scenes.
Rules for EVERY image:
- One separate image per scene, 16:9 landscape (1536x1024).
- NO text, letters, numbers (except price numbers if the scene says so), logos or watermarks. Charts drawn inside scenes must be simple shapes only with NO readable text.
- Keep the characters IDENTICAL to the character reference sheet: [TRADER] and [DR AARON].
- Style: hand-drawn 2D cartoon in a thick-outline doodle-explainer style (same as our Ice Age videos): simple stick-figure characters with round white heads, dot eyes and expressive faces, thin black limbs, messy hair; painterly flat colours with soft gradients and warm cinematic lighting; detailed backgrounds (screens, desks, chart sketches, props); clear foreground / midground / background depth.
- Palette: dark navy and teal backgrounds with warm gold accents, green for buying/support, red for selling/resistance.
- Write the number before each image (for example "Image 010"). Generate the whole batch without asking questions. When done write "Batch done".

# STEP 2 - character reference sheet (generate first and keep it in the chat)

Character reference sheet, hand-drawn 2D doodle-explainer cartoon, plain light background, two full-body characters side by side, NO text: (1) [TRADER]: round white head, dot eyes, short messy dark-brown hair, blue T-shirt, blue jeans, white sneakers, thin black limbs; (2) [DR AARON]: round white head, dot eyes, round glasses, short neat dark hair, navy blazer over a white shirt, friendly smile, holds a marker. 16:9.

# STEP 3 - paste each batch file, save every image as its scene number (010.png, 011.png ...), put them all in ONE folder, zip it and send it to me.
Chart scenes have NO image: they are filled with your real chart recordings (see chart_shot_list.md).
"""
open(out+'/00_MASTER_PROMPT.md','w').write(MASTER)
rows=[];figs=[]
for k in range(1,116):
    m,a,b=S[k];rows.append((k,m,P[k-1],a,b))
    if m=='F':figs.append((k,a,b))
open(out+'/narration_for_voiceover.txt','w').write("\n\n".join(P)+"\n")
with open(out+'/scene_plan.csv','w',newline='') as f:
    w=csv.writer(f);w.writerow(['scene','type','narration','label_or_chart','prompt_or_chart_request']);w.writerows(rows)
# batches of 15
for i in range(0,len(figs),15):
    ch=figs[i:i+15]
    with open(f"{out}/chatgpt-batches/batch_{i//15+1:02d}.txt",'w') as f:
        for k,a,b in ch: f.write(f"Image {k:03d}: {b}\n\n")
# chart shot list
groups={}
for k,(m,a,b) in S.items():
    if m=='C':groups.setdefault(a,[]).append((k,b))
md=["# Chart shot list (your real charts)\n","One recording or screenshot sequence per group. Record each at 16:9 (1920x1080), chart filling most of the frame, clean (hide your account, watchlist and notifications). Where a group says 'replay', screen-record the candles playing forward.\n"]
for g in sorted(groups):
    items=groups[g];first=items[0][0];last=items[-1][0]
    md.append(f"## Chart {g}: scenes {first}-{last}\n")
    for k,b in items:md.append(f"- **Scene {k}** (\"{P[k-1][:70]}...\"): {b}")
    md.append("")
open(out+'/chart_shot_list.md','w').write("\n".join(md))
# human-readable scene plan
pl=["# Gopipways zones video: scene plan\n",f"115 scenes: {len(figs)} stick-figure images + {115-len(figs)} real-chart slots (in {len(groups)} chart groups). Script: 2,542 words, about 17 minutes.\n"]
for k,m,n,a,b in rows:
    pl.append(f"**{k:03d} [{ 'IMAGE' if m=='F' else 'CHART '+a }]** {n}\n  - {'label: '+a if m=='F' else 'show: '+b}\n")
open(out+'/scene_plan.md','w').write("\n".join(pl))
z=zipfile.ZipFile('gopipways-zones-pack.zip','w',zipfile.ZIP_DEFLATED)
for r,_,fs in os.walk(out):
    for fn in fs:z.write(os.path.join(r,fn))
z.close()
print(len(figs),len(groups),[len(v) for v in groups.values()])
