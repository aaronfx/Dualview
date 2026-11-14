"""Generate all 149 scene images with the OpenAI Images API and save them in ONE folder + a zip.
Setup:  pip install openai
        export OPENAI_API_KEY=sk-...        (Windows: set OPENAI_API_KEY=sk-...)
Run:    python generate_images.py           (safe to re-run: it skips images that already exist)
Output: ./images/001.png ... 149.png and ./ice-age-images.zip
"""
import csv, base64, os, sys, time, zipfile
from openai import OpenAI

MODEL = "gpt-image-1"
SIZE = "1536x1024"        # 16:9-ish landscape
QUALITY = "medium"        # use "high" for best quality (costs more)
HERE = os.path.dirname(os.path.abspath(__file__))
client = OpenAI()
os.makedirs(os.path.join(HERE, "images"), exist_ok=True)

def save(b64, path):
    with open(path, "wb") as f:
        f.write(base64.b64decode(b64))

# 1) character sheet (used as a reference so the faces stay consistent)
sheet = os.path.join(HERE, "images", "_character_sheet.png")
if not os.path.exists(sheet):
    prompt = open(os.path.join(HERE, "character_sheet_prompt.txt"), encoding="utf8").read()
    r = client.images.generate(model=MODEL, prompt=prompt, size=SIZE, quality=QUALITY)
    save(r.data[0].b64_json, sheet)
    print("character sheet done")

# 2) scenes
rows = list(csv.DictReader(open(os.path.join(HERE, "..", "ice-age-image-prompts.csv"), encoding="utf8")))
for row in rows:
    out = os.path.join(HERE, "images", row["file"])
    if os.path.exists(out):
        continue
    prompt = row["full_prompt"] + " Keep the characters identical to the reference image."
    for attempt in range(3):
        try:
            with open(sheet, "rb") as ref:
                r = client.images.edit(model=MODEL, image=[ref], prompt=prompt, size=SIZE, quality=QUALITY)
            save(r.data[0].b64_json, out)
            print("saved", row["file"])
            break
        except Exception as e:
            print("retry", row["file"], e)
            time.sleep(10 * (attempt + 1))

# 3) zip
zpath = os.path.join(HERE, "ice-age-images.zip")
with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
    for n in sorted(os.listdir(os.path.join(HERE, "images"))):
        if n[0].isdigit():
            z.write(os.path.join(HERE, "images", n), n)
print("zip ready:", zpath)
