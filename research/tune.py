"""Train/test tuning: fit parameters on OLDER curator lists, evaluate on RECENT curator lists + JAT.

Also tests letting drawback perks go negative.
"""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("BD_DATA", os.path.join(HERE, "data"))
import itertools
import re
import sys
from bisect import bisect_left
from collections import defaultdict

SP = HERE
sys.path.insert(0, SP)
exec(open(f"{SP}/gearscore_v2.py").read())
from wishlists import parse  # noqa: E402
from common import norm  # noqa: E402

MODERN = re.compile(r"renegades|rite of the nine|podcast|monument|final shape|edge of fate|ash|lawless|machine guns", re.I)
# Perks whose description carries a real drawback in that mode (from Clarity text, hand-checked).
DRAWBACK = {
    "pve": {"iron reach", "iron grip", "iron gaze", "backup plan"},
    "pvp": {"iron reach", "iron grip", "iron gaze"},
}

name_to_key = {}
for mode, db in DBS.items():
    m = {}
    for k, w in db.items():
        m[norm(w["name"])] = k
        m.setdefault(norm(re.sub(r"\(.*?\)", "", w["name"])), k)
    name_to_key[mode] = m

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
    split = "jat" if r["source"] == "jat" else ("test" if MODERN.search(r["title"]) else "train")
    for a in p3:
        for b in p4:
            groups[(split, r["mode"], k)].add((a, b))

# Precompute raw ingredients per weapon: listed rank, LOO strength, reference strength.
ING = {}
for (split, mode, k) in groups:
    if (mode, k) in ING:
        continue
    w = DBS[mode][k]
    _, _, s3, s4 = VALS[mode][k]
    def col(c, recs, s):
        ref = max(sum(s[p] for p in recs) / len(recs), 1e-6)
        return {p: (recs.index(p) if p in recs else None, s[p] / ref) for p in c}
    ING[(mode, k)] = (col(w["c3"], w["r3"], s3), col(w["c4"], w["r4"], s4))


def values(col, mode, decay, cap, gamma, neg):
    out = {}
    for p, (rank, rel) in col.items():
        if rank is not None:
            out[p] = max(1 - decay * rank, 0.7)
        elif neg and p in DRAWBACK[mode]:
            out[p] = neg
        else:
            out[p] = cap * min(1.0, rel) ** gamma
    return out


def combine(a, b, p):
    pos = pmean(max(a, 0.0), max(b, 0.0), p) if (a > 0 and b > 0) or p > 0 else 0.0
    return pos + min(a, 0.0) + min(b, 0.0)  # negative perks subtract outright


def auc(pos, neg):
    neg_sorted = sorted(neg)
    tot = 0.0
    for x in pos:
        lo = bisect_left(neg_sorted, x)
        hi = bisect_left(neg_sorted, x + 1e-12)
        tot += lo + 0.5 * (hi - lo)
    return tot / (len(pos) * len(neg_sorted))


def evaluate(params, split):
    decay, cap, gamma, p, neg = params
    by_mode = defaultdict(list)
    for (sp, mode, k), endorsed in groups.items():
        if sp != split:
            continue
        c3, c4 = ING[(mode, k)]
        v3, v4 = values(c3, mode, decay, cap, gamma, neg), values(c4, mode, decay, cap, gamma, neg)
        pos, rest = [], []
        for a in v3:
            for b in v4:
                (pos if (a, b) in endorsed else rest).append(combine(v3[a], v4[b], p))
        if pos and rest:
            by_mode[mode].append(auc(pos, rest))
    return {m: sum(v) / len(v) for m, v in by_mode.items()}


GRID = list(itertools.product([0.04, 0.08, 0.15], [0.6, 0.7, 0.85], [0.3, 0.5, 0.8], [0.0, 0.5, 1.0], [0]))
CURRENT = (0.08, 0.7, 0.5, 0.5, 0)
train = {g: evaluate(g, "train") for g in GRID}
best = {m: max(GRID, key=lambda g: train[g][m]) for m in ("pve", "pvp")}
print("current params (decay .08, cap .7, gamma .5, p .5):")
for sp in ("train", "test", "jat"):
    print(f"  {sp:5s}", {m: round(v, 3) for m, v in evaluate(CURRENT, sp).items()})
for m, g in best.items():
    print(f"best on train for {m}: decay {g[0]}, cap {g[1]}, gamma {g[2]}, p {g[3]} -> "
          f"train {train[g][m]:.3f}, test {evaluate(g, 'test')[m]:.3f}, jat {evaluate(g, 'jat')[m]:.3f}")
spread = {m: (min(train[g][m] for g in GRID), max(train[g][m] for g in GRID)) for m in ("pve", "pvp")}
print("train AUC range across whole grid:", {m: (round(a, 3), round(b, 3)) for m, (a, b) in spread.items()})

print("\nDrawback perks allowed to go negative (value -0.15, subtracted outright):")
for sp in ("train", "test", "jat"):
    base = evaluate(CURRENT, sp)
    negv = evaluate(CURRENT[:4] + (-0.15,), sp)
    print(f"  {sp:5s} " + ", ".join(f"{m}: {base[m]:.4f} -> {negv[m]:.4f}" for m in base))
affected = sum(any(p in DRAWBACK[mode] for p in list(ING[(mode, k)][0]) + list(ING[(mode, k)][1])) for (mode, k) in ING)
print(f"  weapons whose pool contains a drawback perk: {affected} / {len(ING)}")
