"""Per-mode settings for formula + recency-weighted curator votes, honest split.

Stats (curator votes) learned on pre-Edge-of-Fate lists (eras 4-7).
PvE: select on Edge of Fate / Ash & Iron lists (era 3), test once on Renegades + MoT lists (eras 1-2).
PvP: post-EoF PvP lists are too few to select on (era 3 has none), and PvP agreement was flat across eras,
     so select on Final Shape era lists (era 4, learning votes from eras 5-7 only), test on eras 1-3 + JAT.
"""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("BD_DATA", os.path.join(HERE, "data"))
import itertools
import math
from collections import Counter, defaultdict

exec(open(os.path.join(HERE, "era_backtest.py")).read().split("CUR = ")[0])
from itertools import product  # noqa: E402

K_M = 10.0


def col_ing(mode, k):
    if (mode, k) in ING:
        return ING[(mode, k)]
    w = DBS[mode][k]
    _, _, s3, s4 = VALS[mode][k]

    def col(c, recs, s):
        ref = max(sum(s[p] for p in recs) / len(recs), max((s[p] for p in c if p not in recs), default=0), 1e-6)
        return {p: (recs.index(p) if p in recs else None, s[p] / ref) for p in c}

    ING[(mode, k)] = (col(w["c3"], w["r3"], s3), col(w["c4"], w["r4"], s4))
    return ING[(mode, k)]


def learn_votes(groups_, mode, rdecay):
    n, e = Counter(), Counter()
    eras = [int(g[0][0]) for g, _ in groups_]
    newest = min(eras) if eras else 0
    for (era, m, k), endorsed in groups_:
        if m != mode:
            continue
        wgt = rdecay ** (int(era[0]) - newest)
        w = DBS[mode][k]
        end = {p for pair in endorsed for p in pair}
        for p in set(w["c3"]) | set(w["c4"]):
            n[p] += wgt
            e[p] += wgt * (p in end)
    prior = sum(e.values()) / max(1e-9, sum(n.values()))
    return {p: (e[p] + K_M * prior) / (n[p] + K_M) for p in n}, prior


def evaluate_cfg(groups_, mode, cfg, votes, cold=None):
    decay, cap, gamma, p, mu = cfg
    vt, prior = votes
    res = []
    for (era, m, k), endorsed in groups_:
        if m != mode or (cold is not None and (m, k) in cold):
            continue
        c3, c4 = col_ing(mode, k)
        v3, v4 = values(c3, mode, decay, cap, gamma, 0), values(c4, mode, decay, cap, gamma, 0)
        pos, neg = [], []
        for a, b in product(v3, v4):
            if a == b:
                continue
            s = combine(v3[a], v4[b], p)
            if mu:
                s += mu * pmean(vt.get(a, prior), vt.get(b, prior))
            (pos if (a, b) in endorsed else neg).append(s)
        if pos and neg:
            res.append(auc(pos, neg))
    return (sum(res) / len(res), len(res)) if res else (float("nan"), 0)


items = list(eg.items())
by_era = lambda prefixes: [(g, e) for g, e in items if g[0].startswith(prefixes)]
GRID = list(product([0.1, 0.15, 0.2, 0.3], [0.6, 0.7, 0.85], [0.6, 0.8, 1.0, 1.3], [0.0, 0.5, 1.0], [0.0, 0.5, 1.0, 2.0, 4.0]))
CURRENT = (0.08, 0.7, 0.5, 0.5, 0.0)
plan = {
    "pve": dict(learn=by_era(("4", "5", "6", "7")), val=by_era(("3",)), learn_final=by_era(("4", "5", "6", "7")),
                tests={"Renegades+MoT curators": by_era(("1", "2"))}),
    "pvp": dict(learn=by_era(("5", "6", "7")), val=by_era(("4",)), learn_final=by_era(("4", "5", "6", "7")),
                tests={"post-EoF curators": by_era(("1", "2", "3")), "JAT (Dec 2025)": by_era(("0",))}),
}
for mode, pl in plan.items():
    best = None
    for rdecay in (1.0, 0.6):
        votes = learn_votes(pl["learn"], mode, rdecay)
        for cfg in GRID:
            a, n = evaluate_cfg(pl["val"], mode, cfg, votes)
            if best is None or a > best[0]:
                best = (a, cfg, rdecay, n)
    a_val, cfg, rdecay, n_val = best
    print(f"\n=== {mode} ===")
    print(f"best on validation ({n_val} lists): rank decay {cfg[0]}, cap {cfg[1]}, gamma {cfg[2]}, p {cfg[3]}, "
          f"votes weight {cfg[4]}, vote recency decay {rdecay}  -> val AUC {a_val:.3f}")
    cur_val = evaluate_cfg(pl["val"], mode, CURRENT, learn_votes(pl["learn"], mode, 1.0))[0]
    print(f"current shared settings on validation: {cur_val:.3f}")
    votes_final = learn_votes(pl["learn_final"], mode, rdecay)
    seen = {(g[1], g[2]) for g, _ in pl["learn_final"]}
    for name, ds in pl["tests"].items():
        for cold, tag in ((None, "all guns"), (seen, "unseen guns")):
            cur = evaluate_cfg(ds, mode, CURRENT, votes_final, cold)
            new = evaluate_cfg(ds, mode, cfg, votes_final, cold)
            print(f"  TEST {name:24s} {tag:11s}: current {cur[0]:.3f} -> tuned {new[0]:.3f}  (n={new[1]})")
