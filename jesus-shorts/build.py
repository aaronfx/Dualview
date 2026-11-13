import csv,os,shutil,zipfile,re
from data import S,MASTER
out='pack'; shutil.rmtree(out,ignore_errors=True); os.makedirs(out)
open(f'{out}/00_MASTER_PROMPT.md','w').write("# Jesus Shorts – master prompt\n\n"+MASTER+"\n\nUse: paste the style lock once per chat, then send the numbered prompts of ONE short as a batch. Generate a character-sheet image first ([JESUS-DISGUISED] and [JESUS-REVEALED] side by side) and keep it in the same chat so faces stay the same.\n")
rows=[];plan=["# Jesus Shorts – batch 1 (Problem → Helping → Reward)\n","Formula: Jesus appears disguised as someone in need → a person helps with no idea who he is → reward arrives → closing line reveals who he was. 12–13 scenes, ~40–47 s, 1080×1920, ~3 s per image.\n",
"These are **original parable-style stories**, not Gospel accounts. They are inspired by Matthew 25:35-40 (\"I was a stranger and you took me in\") and Hebrews 13:2; the YouTube description must say so, so viewers aren't told these events are in the Bible.\n",
"| # | Title | Words | ~Seconds | Verse |\n|---|---|---|---|---|"]
for s in S:
    n=len(s['scenes']);words=sum(len(a.split()) for a,_ in s['scenes'])
    d=f"{out}/short{s['id']}";os.makedirs(d)
    open(f"{d}/narration_for_elevenlabs.txt",'w').write("\n\n".join(a for a,_ in s['scenes'])+"\n")
    with open(f"{d}/image_prompts.md",'w') as f:
        f.write(f"# Short {s['id']}: {s['title']}\n\n(After the style lock, send each as: 'Image NN: …'. {n} images.)\n\n")
        for i,(a,p) in enumerate(s['scenes'],1):
            f.write(f"**Image {i:02d}** (narration: \"{a}\")\n{p}\n\n"); rows.append((s['id'],i,a,p))
    plan.append(f"| {s['id']} | {s['title']} | {words} | {round(words/2.6)} | {s['verse']} |")
    open(f"{d}/youtube_meta.txt",'w').write(f"TITLE: {s['title']} #shorts\n\nDESCRIPTION:\nA short original parable-style story inspired by {s['verse']} (not a Gospel account). When we help someone in need, we may be serving Jesus himself.\n\n#Jesus #Faith #Christian #Shorts #Kindness #Parable\n")
with open(f'{out}/all_prompts.csv','w',newline='') as f:
    w=csv.writer(f);w.writerow(['short','image','narration','prompt']);w.writerows(rows)
plan.append("\n## Workflow\n1. Paste the master prompt in ChatGPT, make the character sheet.\n2. Generate one short's images (12–13) in that chat, name them 01, 02….\n3. Make the narration in ElevenLabs (Ron, same voice) from that short's narration file.\n4. Send me mp3 + the images; I build the 1080×1920 video with Ken Burns, yellow keyword labels and captions.\n")
open(f'{out}/plan.md','w').write("\n".join(plan))
z=zipfile.ZipFile('jesus-shorts-pack.zip','w',zipfile.ZIP_DEFLATED)
for r,_,fs in os.walk(out):
    for f in fs: z.write(os.path.join(r,f))
z.close()
print("\n".join(plan[:12]))
