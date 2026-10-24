"""Backtest gear score against curator wishlists (DIM Voltron sources + JAT).

For each (source, weapon, mode): endorsed trait pairs vs every other trait pair on that weapon.
Metric = AUC (prob. a random endorsed pair outscores a random non-endorsed pair), plus hit rates.
"""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("BD_DATA", os.path.join(HERE, "data"))
import re
import sys
from collections import defaultdict

SP = HERE
sys.path.insert(0, SP)
exec(open(f"{SP}/gearscore_v2.py").read())
from wishlists import parse  # noqa: E402
from common import norm  # noqa: E402

MODERN = re.compile(r"renegades|rite of the nine|podcast|monument|final shape|edge of fate|ash|lawless|machine guns", re.I)

name_to_key = {mode: {norm(w["name"]): k for k, w in db.items()} for mode, db in DBS.items()}
for mode, db in DBS.items():
    for k, w in db.items():
        name_to_key[mode].setdefault(norm(re.sub(r"\(.*?\)", "", w["name"])), k)


def scorers(mode, k):
    w = DBS[mode][k]
    v3, v4, s3, s4 = VALS[mode][k]
    bin_ = lambda a, b: (a in w["r3"]) + (b in w["r4"])
    v1 = lambda a, b: ((LISTED[min(w["r3"].index(a), 4)] if a in w["r3"] else 0.15) * (LISTED[min(w["r4"].index(b), 4)] if b in w["r4"] else 0.15)) ** 0.5
    v2 = lambda a, b: pmean(v3[a], v4[b])
    strength_only = lambda a, b: pmean(s3[a], s4[b])  # no sheet info for this weapon at all
    return {"binary (Maxeption-style)": bin_, "v1 (flat floor)": v1, "v2 (current)": v2, "strength only (no sheet)": strength_only}


def auc(pos, neg):
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


rows = parse(DATA + "/ext/wl/voltron.txt", "voltron") + (parse(DATA + "/ext/jat/bundles/DIM/just-another-team-mnk.txt", "jat") if os.path.exists(DATA + "/ext/jat/bundles/DIM/just-another-team-mnk.txt") else [])
groups = defaultdict(set)
for r in rows:
    if r["mode"] not in DBS:
        continue
    k = name_to_key[r["mode"]].get(norm(r["weapon"])) or name_to_key[r["mode"]].get(norm(re.sub(r"\(.*?\)", "", r["weapon"])))
    if not k:
        continue
    w = DBS[r["mode"]][k]
    p3 = [p for p in r["perks"] if p in w["c3"]]
    p4 = [p for p in r["perks"] if p in w["c4"]]
    if not p3 or not p4:
        continue
    if r["source"] == "jat":
        src = "JAT (built from Aegis)"
    else:
        src = "Voltron curators, recent (2024-26)" if MODERN.search(r["title"]) else "Voltron curators, older (S10-S20)"
    for a in p3:
        for b in p4:
            groups[(src, r["mode"], k)].add((a, b))

res = defaultdict(lambda: defaultdict(list))
hits = defaultdict(lambda: [0, 0, 0, 0])
for (src, mode, k), endorsed in groups.items():
    w = DBS[mode][k]
    pairs = [(a, b) for a in w["c3"] for b in w["c4"]]
    rest = [p for p in pairs if p not in endorsed]
    if not rest:
        continue
    for name, f in scorers(mode, k).items():
        res[(src, mode)][name].append(auc([f(*p) for p in endorsed], [f(*p) for p in rest]))
    v3, v4, _, _ = VALS[mode][k]
    sc = lambda p: 100 * pmean(v3[p[0]], v4[p[1]])
    h = hits[(src, mode)]
    h[0] += sum(sc(p) >= 75 for p in endorsed); h[1] += len(endorsed)
    h[2] += sum(sc(p) >= 75 for p in rest); h[3] += len(rest)

print(f"{'source':38s} {'mode':4s} {'weapons':>7s}  " + "  ".join(f"{n[:22]:>22s}" for n in next(iter(res.values()))))
for (src, mode), d in sorted(res.items()):
    n = len(next(iter(d.values())))
    print(f"{src:38s} {mode:4s} {n:7d}  " + "  ".join(f"{sum(v) / len(v):22.3f}" for v in d.values()))
print("\nv2 hit rates (score >= 75):")
for (src, mode), h in sorted(hits.items()):
    print(f"  {src:38s} {mode}: curated pairs {h[0] / h[1]:.0%} | non-curated pairs {h[2] / h[3]:.0%}")
