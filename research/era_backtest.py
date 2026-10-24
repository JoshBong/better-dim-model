"""Patch-aware backtest: score each curator source against the CURRENT (Monument of Triumph) model, bucketed by
the patch era the source was written in. If accuracy falls with age, the 'misses' are meta drift, not model error.
"""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("BD_DATA", os.path.join(HERE, "data"))
import re
import sys
from collections import defaultdict

SP = HERE
sys.path.insert(0, SP)
exec(open(f"{SP}/tune.py").read().split("GRID = ")[0])

ERAS = [  # newest first; first match wins
    ("1 Monument of Triumph (Jun 2026+)", r"pve podcast 1(6[5-9]|7\d)|machine guns|guardian games 2026|iron banner 2026|ab rolls 4\d"),
    ("2 Renegades / Lawless (Dec 2025-Jun 2026)", r"renegades|lawless|equilibrium|pve podcast 16[0-4]|arms week 2026|dawning 2025"),
    ("3 Edge of Fate / Ash & Iron (Jul-Dec 2025)", r"edge of fate|kepler|ash (and|&) iron|pve podcast 15\d"),
    ("4 Final Shape episodes (Jun 2024-Jul 2025)", r"final shape|revenant|heresy|echoes|rite of the nine|ep13\d|pve podcast 1[34]\d|vault of glass weapon refresh"),
    ("5 Lightfall era (2023-24)", r"season 2[0-3]|s2[0-3]\b|defiance|deep|into the light|witch\b|wish|lightfall|guardian games \(2024\)|season 22"),
    ("6 Witch Queen era (2022)", r"\bwq\b|witch queen|s1[6-9]\b|season 1[6-9]|risen|haunted|plunder|seraph|30th|kings fall|vow"),
    ("7 Beyond Light & older (2020-21)", r"s1[0-5]\b|season 1[0-5]|chosen|season of the lost|sharditkeepit|podcast 2\d\d|splicer|hunt\b"),
]


def era_of(title):
    t = title.lower()
    for name, pat in ERAS:
        if re.search(pat, t):
            return name
    return None


eg = defaultdict(set)
cites_aegis = defaultdict(lambda: [0, 0])
for r in rows:
    if r["mode"] not in DBS:
        continue
    era = "0 JAT, built from Aegis (Dec 2025)" if r["source"] == "jat" else era_of(r["title"])
    if not era:
        continue
    k = name_to_key[r["mode"]].get(norm(r["weapon"])) or name_to_key[r["mode"]].get(norm(re.sub(r"\(.*?\)", "", r["weapon"])))
    if not k:
        continue
    w = DBS[r["mode"]][k]
    p3 = [p for p in r["perks"] if p in w["c3"]]
    p4 = [p for p in r["perks"] if p in w["c4"]]
    if not p3 or not p4:
        continue
    c = cites_aegis[era]
    c[0] += "aegis" in r["notes"].lower()
    c[1] += 1
    for a in p3:
        for b in p4:
            eg[(era, r["mode"], k)].add((a, b))

CUR = (0.08, 0.7, 0.5, 0.5, 0)
out = defaultdict(lambda: defaultdict(list))
for (era, mode, k), endorsed in eg.items():
    c3, c4 = ING.get((mode, k)) or (None, None)
    if c3 is None:
        w = DBS[mode][k]; _, _, s3, s4 = VALS[mode][k]
        def col(c, recs, s):
            ref = max(sum(s[p] for p in recs) / len(recs), 1e-6)
            return {p: (recs.index(p) if p in recs else None, s[p] / ref) for p in c}
        c3, c4 = col(w["c3"], w["r3"], s3), col(w["c4"], w["r4"], s4)
    v3, v4 = values(c3, mode, *CUR[:3], 0), values(c4, mode, *CUR[:3], 0)
    w = DBS[mode][k]
    pos, rest, bpos, brest = [], [], [], []
    for a in v3:
        for b in v4:
            s = combine(v3[a], v4[b], CUR[3])
            bs = (a in w["r3"]) + (b in w["r4"])
            if (a, b) in endorsed:
                pos.append(s); bpos.append(bs)
            else:
                rest.append(s); brest.append(bs)
    if pos and rest:
        out[(era, mode)]["v2"].append(auc(pos, rest))
        out[(era, mode)]["sheet"].append(auc(bpos, brest))

print(f"{'era of source':44s} mode  weapons  v2 AUC  sheet-only AUC  %rows citing Aegis")
for (era, mode), d in sorted(out.items()):
    ca = cites_aegis[era]
    print(f"{era:44s} {mode:4s} {len(d['v2']):7d}  {sum(d['v2']) / len(d['v2']):.3f}   {sum(d['sheet']) / len(d['sheet']):.3f}"
          f"          {ca[0] / max(ca[1], 1):.0%}")
