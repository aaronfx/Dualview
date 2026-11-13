import csv,os,shutil,zipfile,re
from data import S,MASTER
out='pack'; shutil.rmtree(out,ignore_errors=True); os.makedirs(out)
open(f'{out}/00_MASTER_PROMPT.md','w').write("# Jesus Shorts – master prompt\n\n"+MASTER+"\n")
rows=[];plan=["# Jesus Shorts – batch 1 (Problem → Helping → Reward)\n","Formula (copied from the channel's winning Short): Jesus is NAMED in the hook as a poor stranger → people refuse → a child or poor person helps despite an unanswered prayer → his footprints glow → the prayer is answered → \"They had welcomed their Savior.\" Visual style = Past Survivor / Ice Age doodle-explainer painted illustration, vertical 9:16 (1080×1920), yellow outlined keyword label on each scene, sentence captions, Ken Burns motion, ~3.5 s per image. Narrator: same ElevenLabs voice as the winning Short (Mark).\n",
"These are **original parable-style stories**, not Gospel accounts. They are inspired by Matthew 25:35-40 (\"I was a stranger and you took me in\") and Hebrews 13:2; the YouTube description must say so, so viewers aren't told these events are in the Bible.\n",
"| # | Title | Words | ~Seconds | Verse |\n|---|---|---|---|---|"]
for s in S:
    n=len(s['scenes']);words=sum(len(x[0].split()) for x in s['scenes'])
    d=f"{out}/short{s['id']}";os.makedirs(d)
    open(f"{d}/narration_for_elevenlabs.txt",'w').write("\n\n".join(x[0] for x in s['scenes'])+"\n")
    with open(f"{d}/image_prompts.md",'w') as f:
        f.write(f"# Short {s['id']}: {s['title']}\n\n(After the style lock, send each as: 'Image NN: …'. {n} images.)\n\n")
        for i,(a,l,p) in enumerate(s['scenes'],1):
            f.write(f"**Image {i:02d}** (narration: \"{a}\"; yellow label: {l})\n{p}\n\n"); rows.append((s['id'],i,a,l,p))
    plan.append(f"| {s['id']} | {s['title']} | {words} | {round(words/2.6)} | {s['verse']} |")
    open(f"{d}/youtube_meta.txt",'w').write(f"TITLE: {s['title']} #shorts\n\nDESCRIPTION:\nA short original, fictional story inspired by {s['verse']} (not a Gospel account). When we help someone in need, we may be serving Jesus himself.\n\n#Jesus #Faith #Christian #Shorts #Kindness #Parable\n")
with open(f'{out}/all_prompts.csv','w',newline='') as f:
    w=csv.writer(f);w.writerow(['short','image','narration','yellow_label','prompt']);w.writerows(rows)
plan.append("\n## Workflow\n1. Paste the master prompt in ChatGPT, make the character sheet.\n2. Generate one short's images (12–13) in that chat, name them 01, 02….\n3. Make the narration in ElevenLabs (Ron, same voice) from that short's narration file.\n4. Send me mp3 + the images; I build the 1080×1920 video with Ken Burns, yellow keyword labels and captions.\n")
open(f'{out}/plan.md','w').write("\n".join(plan))
z=zipfile.ZipFile('jesus-shorts-pack.zip','w',zipfile.ZIP_DEFLATED)
for r,_,fs in os.walk(out):
    for f in fs: z.write(os.path.join(r,f))
z.close()
print("\n".join(plan[:12]))
