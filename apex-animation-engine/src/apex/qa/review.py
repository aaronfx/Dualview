"""Creative review: a repeatable human rubric, kept separate from objective technical metrics.

`build_review_packet` writes, next to a render:
  REVIEW.md            objective metrics (from QA, labelled as such) + the human rubric with scoring anchors + a per-shot
                       notes table + (optional) AI Director suggestions
  review_scores.json   a blank score sheet, one per reviewer (`reviewers/<name>.json`), aggregated by `aggregate_scores`

Rules:
- Technical checks prove correctness (no teleporting joints, synced audio, ...). They never prove artistic quality.
- Only human reviewers score the rubric. The AI Director may *suggest corrections* from rendered previews; its
  output is labelled as suggestions and carries no score.
"""
from __future__ import annotations

import json
import os
import statistics
from typing import Dict, List, Optional

CRITERIA = [
    ("character_acting", "Character acting",
     {3: "poses are generic; reactions missing or mechanical", 5: "clear intent in key beats; timing uniform; acting reads only in close-ups",
      7: "distinct, motivated reactions; varied timing; anticipation and follow-through visible", 9: "specific, surprising, consistent personality; every beat earns its time"}),
    ("action_choreography", "Action choreography and body mechanics",
     {3: "weight absent; contacts slide or float", 5: "physically plausible; impacts read; some floaty or stiff moments",
      7: "strong lines of action, clear arcs, convincing weight shifts and contacts", 9: "dynamic, inventive staging with flawless weight and contact"}),
    ("camera_clarity", "Camera clarity and staging",
     {3: "action leaves frame or is confusing; disorienting moves", 5: "action readable; some shots too wide/tight or moves unmotivated",
      7: "every shot has a purpose; spatial orientation always clear", 9: "camera amplifies the story; cutting rhythm feels authored"}),
    ("visual_consistency", "Visual consistency and art direction",
     {3: "inconsistent style; artefacts", 5: "coherent style; flat lighting or noisy effects",
      7: "consistent, attractive style; effects support the action", 9: "distinctive, polished look throughout"}),
    ("sound_quality", "Sound quality and sync",
     {3: "missing or wrong sounds", 5: "sync correct; sounds synthetic or thin", 7: "layered, believable sound with a supporting score",
      9: "sound design adds character and drama"}),
    ("story_coherence", "Story coherence",
     {3: "the viewer cannot follow what happens or why", 5: "the plot is followable with effort",
      7: "cause and effect obvious without narration", 9: "tight, satisfying arc with set-ups that pay off"}),
    ("emotional_readability", "Emotional readability",
     {3: "the character's feelings cannot be read", 5: "major emotions readable", 7: "emotional arc clear and felt",
      9: "the audience feels with the character throughout"}),
]


def _metrics_section(qa: Optional[dict]) -> List[str]:
    L = ["## A. Objective technical metrics (correctness, not quality)", ""]
    if not qa:
        return L + ["No QA report supplied.", ""]
    k = qa.get("counts", {})
    L.append(f"QA: **{'PASSED' if qa.get('passed') else 'FAILED'}**, {k.get('total', len(qa.get('checks', [])))} checks "
             f"({', '.join(f'{v} {s}' for s, v in sorted(k.get('by_status', {}).items()))}).")
    L += ["", "| Check | Status | Metric | Threshold |", "|---|---|---|---|"]
    for c in qa.get("checks", []):
        if c["name"].startswith("exit["):
            continue
        m = "" if c.get("metric") is None else f"{c['metric']:.4g}"
        th = "" if c.get("threshold") is None else f"{c['threshold']:.4g}"
        L.append(f"| {c['name']} | {c['status']} | {m} | {th} |")
    return L + ["", "These numbers show the animation is technically valid. They say nothing about how good it is.", ""]


def _rubric_section(shots) -> List[str]:
    L = ["## B. Human review rubric (score 1-10 per criterion; anchors below)", "",
         "Review the full-resolution video at least twice (once for story, once frame by frame). Score each criterion against the anchors, "
         "then note concrete fixes with timestamps. Each reviewer fills one `review_scores.json` copy.", ""]
    for key, title, anchors in CRITERIA:
        L.append(f"### {title} (`{key}`)")
        L += [f"- **{s}**: {d}" for s, d in sorted(anchors.items())]
        L += ["", "Score: ____   Notes / timestamps:", ""]
    L += ["### Per-shot notes", "", "| Shot | Time | What works | What to fix |", "|---|---|---|---|"]
    for sh in shots:
        L.append(f"| {sh.id} | {sh.start:.2f}-{sh.end:.2f} | | |")
    return L + [""]


AI_SYSTEM = ("You are an animation director reviewing a rendered stick-figure animation from its shot list, event timeline "
             "and QA notes. Suggest at most 8 concrete corrections (timestamp, problem, fix). Do NOT give any score or quality "
             "rating; your output is advisory only.")


def ai_suggestions(project, scene_id: str, qa: Optional[dict], events: List[dict]) -> Optional[str]:
    """Ask the configured AI Director (OpenRouter etc.) for correction suggestions. Returns None when no provider."""
    from ..ai.providers import provider_from_env
    prov = provider_from_env()
    if prov is None:
        return None
    sc = project.scene(scene_id)
    shots = "\n".join(f"{s.id} {s.start:.2f}-{s.end:.2f} {s.kind}: {s.description}" for s in sc.shots)
    ev = "\n".join(f"{e['t']:.2f} {e['type']}" for e in events[:120])
    warn = "\n".join(f"{c['name']}: {c['status']}" for c in (qa or {}).get("checks", []) if c["status"] != "PASS")
    return prov.complete(AI_SYSTEM, f"SHOTS:\n{shots}\n\nEVENTS:\n{ev}\n\nNON-PASSING CHECKS:\n{warn or 'none'}", max_tokens=1500)


def build_review_packet(project, scene_id: str, out_dir: str, video: Optional[str] = None, qa_json: Optional[str] = None,
                        events: Optional[List[dict]] = None, with_ai: bool = False) -> str:
    os.makedirs(out_dir, exist_ok=True)
    qa = json.load(open(qa_json)) if qa_json and os.path.exists(qa_json) else None
    sc = project.scene(scene_id)
    L = [f"# Review packet: {project.title} / {scene_id}", ""]
    if video:
        L += [f"Video under review: `{os.path.basename(video)}`", ""]
    L += _metrics_section(qa) + _rubric_section(sc.shots)
    L += ["## C. AI Director suggestions (advisory; not a score)", ""]
    text = ai_suggestions(project, scene_id, qa, events or []) if with_ai else None
    L += [text if text else "Not generated (no AI provider configured, or not requested). Suggestions never replace human scores.", ""]
    md = os.path.join(out_dir, "REVIEW.md")
    with open(md, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    sheet = {"video": os.path.basename(video) if video else None, "reviewer": "", "scores": {k: None for k, _, _ in CRITERIA},
             "notes": {k: "" for k, _, _ in CRITERIA}, "shots": {s.id: "" for s in sc.shots}}
    with open(os.path.join(out_dir, "review_scores.json"), "w", encoding="utf-8") as fh:
        json.dump(sheet, fh, indent=1)
    return md


def aggregate_scores(sheets: List[dict]) -> Dict[str, dict]:
    """Combine reviewers' sheets: per criterion mean, spread and count (unscored criteria are ignored)."""
    out = {}
    for k, title, _ in CRITERIA:
        vals = [float(s["scores"][k]) for s in sheets if s.get("scores", {}).get(k) is not None]
        out[k] = {"title": title, "n": len(vals), "mean": round(statistics.mean(vals), 2) if vals else None,
                  "spread": round(max(vals) - min(vals), 2) if len(vals) > 1 else 0.0}
    return out
