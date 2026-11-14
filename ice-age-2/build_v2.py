import csv,json,os,zipfile,sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from script_data import V
OUT='/home/user/Dualview/scripts/video2-fire-went-out'
os.makedirs(OUT+'/chatgpt-pack-v2',exist_ok=True)
STYLE=("Hand-drawn 2D cartoon illustration in a thick-outline doodle-explainer style: simple stick-figure characters with round white heads, dot eyes and expressive faces, thin black limbs, messy brown hair; painterly flat colours with soft gradient skies and warm cinematic lighting; richly detailed backgrounds (rock and ice textures, snow, plants, props, tools, tiny details in every corner); clear foreground / midground / background depth; 16:9 widescreen; NO text, NO letters, NO watermark.")
CH={"[YOU]":"a modern man: round white head, short messy dark-brown hair, blue T-shirt, blue jeans, white sneakers, thin black limbs",
"[HUNTER]":"Ice Age father: round white head, messy brown hair, short stubble, brown fur tunic with a fur-trimmed hood, fur boots, bone-tipped spear",
"[MAMA]":"Ice Age mother: round white head, brown hair in a ponytail, tan fur dress, fur boots, bone needle at her belt",
"[KID]":"Ice Age child: smaller, round white head, spiky brown hair, fur vest, big grin",
"[ELDER]":"Ice Age elder: round white head, long grey hair and grey beard, dark fur cloak, wooden staff"}
def full(p):
    for k,v in CH.items():p=p.replace(k,k.strip('[]').title()+" ("+v+")")
    return p
# narration: one scene per paragraph
open(OUT+'/narration_for_elevenlabs.txt','w').write('\n\n'.join(t for t,p in V)+'\n')
json.dump([{'scene':i+1,'text':t} for i,(t,p) in enumerate(V)],open(OUT+'/scene_map.json','w'),indent=1)
# prompts md + csv
md=["# Video 2 image prompts: What Did Ice Age People Do When the Fire Went Out? (%d scenes)\n"%len(V),
"Same STYLE block and character sheet as video 1 (attach the sheet to every prompt). No text in images. Name files 001.jpg/png ... %03d. Scene numbers follow the narration order.\n"%len(V)]
rows=[]
for i,(t,p) in enumerate(V):
    md.append(f"### {i+1:03d}\n*Narration:* {t}\n\n**Prompt:** {p}\n")
    rows.append([f"{i+1:03d}.png",t,STYLE+" "+full(p)])
open(OUT+'/image_prompts.md','w').write('\n'.join(md))
for d in (OUT,OUT+'/chatgpt-pack-v2'):
    with open(d+'/image_prompts.csv','w',newline='') as f:
        w=csv.writer(f);w.writerow(['file','narration','full_prompt']);w.writerows(rows)
# chatgpt pack
sheet=open('/home/user/Dualview/scripts/chatgpt-pack/character_sheet_prompt.txt').read()
master=f"""# STEP 1 - paste this ONCE at the start of a NEW ChatGPT chat

You are my image generator for an animated YouTube video. I will send numbered batches of scenes.
Rules for EVERY image:
- Generate each scene as its own separate image, 16:9 landscape (1536x1024).
- Do NOT put any text, letters, numbers or watermarks in the image.
- Keep the characters IDENTICAL to the character reference sheet I attach (modern man = YOU, Ice Age father, mother, child, elder). Use the SAME sheet as video 1.
- Style for all images: {STYLE}
- Generate the images one after another without asking me questions. Before each image write its number, for example "Image 007".
- When a batch is finished write "Batch done" and wait for my next batch.

# STEP 2 - attach the character sheet from video 1 (or generate it with character_sheet_prompt.txt) and keep it in the chat.

# STEP 3 - paste batch_01.txt, then batch_02.txt ... ({(len(V)+14)//15} batches of 15 scenes)
Save each image by its number (001.png ...), put all in ONE folder, zip it on your computer and send it to me.
"""
open(OUT+'/chatgpt-pack-v2/00_MASTER_PROMPT.md','w').write(master)
open(OUT+'/chatgpt-pack-v2/character_sheet_prompt.txt','w').write(sheet)
for b in range(0,len(V),15):
    ch=V[b:b+15]
    t="Batch %02d - scenes %03d to %03d. Generate each as a separate 16:9 image, no text in the image, characters identical to the sheet.\n\n"%(b//15+1,b+1,b+len(ch))
    for k,(tx,p) in enumerate(ch): t+=f"Image {b+k+1:03d}: {full(p)}\n\n"
    open(OUT+f'/chatgpt-pack-v2/batch_{b//15+1:02d}.txt','w').write(t)
# API script
open(OUT+'/chatgpt-pack-v2/generate_images.py','w').write(open('/home/user/Dualview/scripts/chatgpt-pack/generate_images.py').read().replace('os.path.join(HERE, "..", "ice-age-image-prompts.csv")','os.path.join(HERE, "image_prompts.csv")').replace('ice-age-images.zip','video2-images.zip'))
z=zipfile.ZipFile(OUT+'/chatgpt-pack-v2.zip','w',zipfile.ZIP_DEFLATED)
for n in sorted(os.listdir(OUT+'/chatgpt-pack-v2')):z.write(OUT+'/chatgpt-pack-v2/'+n,'chatgpt-pack-v2/'+n)
z.write(OUT+'/narration_for_elevenlabs.txt','narration_for_elevenlabs.txt')
print(len(V),len(z.namelist()))
