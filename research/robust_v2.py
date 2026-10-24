"""Robustness: do keep/maybe/trash calls survive reasonable parameter changes? + Maxeption agreement."""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("BD_DATA", os.path.join(HERE, "data"))
import random as _r

SRC = open(os.path.join(HERE, "gearscore_v2.py")).read()
base_ns = {}
exec(SRC, base_ns)
DBS = base_ns["DBS"]

_r.seed(3)
ROLLS = {}
for mode, db in DBS.items():
    rows = []
    for key, w in db.items():
        for _ in range(60):
            o3, o4 = [_r.choice(w["c3"])], [_r.choice(w["c4"])]
            b = _r.choice(w["barrels"]) if w["barrels"] else ""
            m = _r.choice(w["mags"]) if w["mags"] else ""
            rows.append((key, o3, o4, b, m))
    ROLLS[mode] = rows


def scores(ns, mode):
    db, vals = ns["DBS"][mode], ns["VALS"][mode]
    return [ns["score"](db[k], vals[k][0], vals[k][1], o3, o4, b, m) for k, o3, o4, b, m in ROLLS[mode]]


def band(x):
    return 0 if x < 55 else (1 if x < 75 else (2 if x < 90 else 3))


def spearman(a, b):
    def rk(v):
        o = sorted(range(len(v)), key=v.__getitem__)
        r = [0.0] * len(v)
        for i, j in enumerate(o):
            r[j] = i
        return r
    ra, rb = rk(a), rk(b)
    n = len(a); ma = sum(ra) / n; mb = sum(rb) / n
    c = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    return c / ((sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5)


base = {m: scores(base_ns, m) for m in DBS}
variants = {
    "p=0 (geo)": "P = 0.5", "p=1 (avg)": "P = 0.5",
    "cap .6": "UNLISTED_CAP = 0.7", "cap .8": "UNLISTED_CAP = 0.7",
    "gamma .3": "GAMMA = 0.5", "gamma .8": "GAMMA = 0.5",
    "steeper listed decay": "LISTED = [1.0, 0.92, 0.85, 0.80, 0.76]",
}
repl = {
    "p=0 (geo)": "P = 0.0", "p=1 (avg)": "P = 1.0", "cap .6": "UNLISTED_CAP = 0.6", "cap .8": "UNLISTED_CAP = 0.8",
    "gamma .3": "GAMMA = 0.3", "gamma .8": "GAMMA = 0.8",
    "steeper listed decay": "LISTED = [1.0, 0.85, 0.75, 0.68, 0.62]",
}
print("Robustness vs baseline (p=.5, cap=.7, gamma=.5): % of rolls whose band changes | Spearman")
for name, old in variants.items():
    ns = {}
    exec(SRC.replace(old, repl[name], 1), ns)
    out = []
    for m in DBS:
        s = scores(ns, m)
        changed = sum(band(a) != band(b) for a, b in zip(base[m], s)) / len(s)
        out.append(f"{m}: {changed:.1%} changed, rho {spearman(base[m], s):.3f}")
    print(f"  {name:22s} " + " | ".join(out))

# Agreement with Maxeption's default grade (binary listed/not + mag/barrel)
GR = {"S+": 6, "S": 5, "A+": 4, "A": 3, "C": 2, "D": 1, "F": 0}


def mx(w, o3, o4, b, m):
    p1, p2 = o3[0] in w["r3"], o4[0] in w["r4"]
    mg, br = m in w["rm"], b in w["rb"]
    if p1 and p2:
        return "S+" if mg and br else "S" if mg else "A+" if br else "A"
    if p1 or p2:
        return "C" if mg or br else "D"
    return "F"


for mode in DBS:
    g = [GR[mx(DBS[mode][k], o3, o4, b, m)] for k, o3, o4, b, m in ROLLS[mode]]
    # Within Maxeption's F grade (neither trait listed), how spread are we?
    f_scores = [s for s, gg in zip(base[mode], g) if gg == 0]
    d_scores = [s for s, gg in zip(base[mode], g) if gg in (1, 2)]
    print(f"\n{mode}: Spearman vs Maxeption grade {spearman(base[mode], g):.3f}")
    for lab, ss in (("Maxeption F (no listed trait)", f_scores), ("Maxeption C/D (one listed trait)", d_scores)):
        ss = sorted(ss)
        print(f"  our scores within {lab}: p10 {ss[len(ss)//10]:.0f}, median {ss[len(ss)//2]:.0f}, p90 {ss[9*len(ss)//10]:.0f}")
