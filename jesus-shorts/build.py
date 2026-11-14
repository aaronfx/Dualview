import csv,os,shutil,zipfile,re
from data import S,MASTER,HOOKS
out='pack'; shutil.rmtree(out,ignore_errors=True); os.makedirs(out)
open(f'{out}/00_MASTER_PROMPT.md','w').write("# Jesus Shorts – master prompt\n\n"+MASTER+"\n")
rows=[];plan=["# Jesus Shorts – batch 1 (Problem → Helping → Reward)\n","Formula (copied from the channel's winning Short): Jesus is NAMED in the hook as a poor stranger → people refuse → a child or poor person helps despite an unanswered prayer → his footprints glow → the prayer is answered → \"They had welcomed their Savior.\" Visual style = Past Survivor / Ice Age doodle-explainer painted illustration, vertical 9:16 (1080×1920), yellow outlined keyword label on each scene, sentence captions, Ken Burns motion, ~2.5 s per image (Short 1 is already reworked to 18 scenes; Shorts 2-5 are still 11-12 scenes and get reworked next). Narrator: same ElevenLabs voice as the winning Short (Mark).\n",
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
    open(f"{d}/hook_overlay.txt",'w').write(f"On-screen hook (big yellow outlined text, first 3-4 seconds): {HOOKS[s['id']]}\n")
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
open(f'{out}/VOICEOVER_GUIDE.md','w').write("""# Voiceover guide (conversion-focused)
Why this version: your winning Short lost 73% of viewers in the first seconds (swiped away) but kept 73.5% average viewed once they stayed. So:
1. **Line 1 is the hook** and carries the whole stake: who he is, what is wrong, and that nobody knew it was Jesus. It's spoken in the first 3-4 seconds.
2. **Short sentences**, one idea per line, one scene per line, so there is always a new picture under every sentence.
3. **Open loop at line 4**: "Then a little girl named Lily stopped." keeps people for the payoff.
4. **Glowing footprints** as the visual peak, then **one whispered recognition line** ("Dad... that was Jesus.") for the emotional hit.
5. **Last line = call to action**: "Type Amen if you believe." Pin a comment saying the same.

ElevenLabs: use the same Mark voice as the winner. Paste the narration file, one line per paragraph. Suggested starting settings (adjust by ear): Stability ~40-50 so it stays emotional, Similarity ~75, Style a little above zero, Speed 1.0-1.05. Keep the recognition line slower and softer (the "..." makes a pause). Target length 40-48 s. If it runs over 50 s, raise speed to 1.05.
Honest note: no script can promise conversions. This applies what your own analytics show; compare retention at 0:03 on the first one and adjust.
""")
import zipfile
z=zipfile.ZipFile('jesus-shorts-pack.zip','w',zipfile.ZIP_DEFLATED)
for r,_,fs in os.walk(out):
    for f in fs: z.write(os.path.join(r,f))
z.close()
