import json,csv
import prompts_b
from prompts_a import P
from prompts_c import C
sc=json.load(open('/tmp/claude-0/ice/scenes.json'))
assert C[46].startswith('Hands passing'); C=C[:46]+C[47:]; assert len(C)==50
F=[None]*149
for i in range(0,47):F[i]=P[i]
m={47:47,49:48,50:49,68:67,69:68}
for i in range(51,68): m[i]=i-1
m.update({70:70,71:71,72:72,73:74,74:75,75:76,76:77,77:78,78:79,79:80,80:81,81:82,82:83,83:84,84:85,85:86,86:87,87:88,88:89,89:90,90:91,91:92,92:93,93:94,94:96,95:97,96:98,97:99,98:100})
for s,p in m.items():F[s]=P[p]
F[48]="[HUNTER] standing proudly in front of the finished mammoth-bone hut with one arm pointing at it and a big grin, [KID] clapping, smoke curling from the roof hole, the bone dome and hide cover clearly visible in detail, dusk snow light and warm glow from the doorway, proud 'that is a house' mood"
for k,x in enumerate(C):F[99+k]=x
assert all(F),[i for i,x in enumerate(F) if not x]
STYLE=("Hand-drawn 2D cartoon illustration in a thick-outline doodle-explainer style: simple stick-figure characters with round white heads, dot eyes and expressive faces, thin black limbs, messy brown hair; painterly flat colours with soft gradient skies and warm cinematic lighting; richly detailed backgrounds (rock and ice textures, snow, plants, props, tools, tiny details in every corner); clear foreground / midground / background depth; 16:9 widescreen; NO text, NO letters, NO watermark.")
CHARS={"[YOU]":"a modern man: round white head, short messy dark-brown hair, blue T-shirt, blue jeans, white sneakers, thin black limbs",
"[HUNTER]":"Ice Age father: round white head, messy brown hair, short stubble, brown fur tunic with a fur-trimmed hood, fur boots, bone-tipped spear",
"[MAMA]":"Ice Age mother: round white head, brown hair in a ponytail, tan fur dress, fur boots, bone needle at her belt",
"[KID]":"Ice Age child: smaller, round white head, spiky brown hair, fur vest, big grin",
"[ELDER]":"Ice Age elder: round white head, long grey hair and grey beard, dark fur cloak, wooden staff"}
md=["# Ice Age video: scene-by-scene image prompts (149 scenes)\n",
"Use with ChatGPT, Midjourney or any image tool. One image per scene, 16:9, **no text in images** (titles and labels are added in the animation).\n",
"## Step 1: paste this STYLE block before every prompt\n```\n"+STYLE+"\n```\n",
"## Step 2: character sheet (generate once, then attach it as a reference image to every prompt)\n"+"\n".join(f"- **{k}** = {v}" for k,v in CHARS.items())+"\n",
"Name files `001.png` ... `149.png` in scene order. Upload them all as one folder or zip.\n","## Scenes\n"]
rows=[]
for i,x in enumerate(F):
    s=sc[i];md.append(f"### {i+1:03d}  ({s['a']:.1f}s - {s['e']:.1f}s)\n*Narration:* {s['text']}\n\n**Prompt:** {x}\n")
    full=x
    for k,v in CHARS.items(): full=full.replace(k,k.strip('[]').title()+" ("+v+")")
    rows.append([f"{i+1:03d}.png",s['a'],s['e'],s['text'],STYLE+" "+full])
open('../scripts/ice-age-image-prompts.md','w').write("\n".join(md))
with open('../scripts/ice-age-image-prompts.csv','w',newline='') as f:
    w=csv.writer(f);w.writerow(['file','start_s','end_s','narration','full_prompt']);w.writerows(rows)
print(len(rows))
for i in (48,64,69,72,98,144,145,148):print(i,'|',sc[i]['text'][:36],'|',F[i][:70])
