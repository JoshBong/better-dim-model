"""Gear score v2: per-weapon score relative to that weapon's best roll; weapon tier kept separate.

Trait value:
  - perk the sheet lists for this weapon at rank i -> LISTED[i]          (1.0, .92, .85, .80, .76)
  - perk not listed -> UNLISTED_CAP * q                                   q = strength percentile among the
                                                                          column's perks, learned from how
                                                                          often the sheets pick it on other
                                                                          weapons of the same type (leave-one-out)
Combine the two trait columns with a power mean (p=P), then a small barrel/mag nudge.
"""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("BD_DATA", os.path.join(HERE, "data"))
import random
import sys
from collections import Counter, defaultdict
from itertools import product

sys.path.insert(0, HERE)
from common import build, load  # noqa: E402

random.seed(11)
LISTED = [1.0, 0.92, 0.85, 0.80, 0.76]
UNLISTED_CAP = 0.7
GAMMA = 0.5
P = 0.5
K_GLOBAL, K_TYPE = 6.0, 4.0

pve_s, pvp_s, by_name = load()
DBS = {"pve": build(pve_s, by_name), "pvp": build(pvp_s, by_name)}


def pick_weight(perk, recs):
    return (1 - 0.15 * recs.index(perk)) if perk in recs else 0.0


def tally(db, exclude=None):
    """Exposure and rank-weighted picks per perk, globally and per weapon type."""
    g_n, g_w = Counter(), Counter()
    t_n, t_w = defaultdict(Counter), defaultdict(Counter)
    for key, w in db.items():
        if key == exclude:
            continue
        for col, recs in ((w["c3"], w["r3"]), (w["c4"], w["r4"])):
            for p in col:
                pw = pick_weight(p, recs)
                g_n[p] += 1
                g_w[p] += pw
                t_n[w["wtype"]][p] += 1
                t_w[w["wtype"]][p] += pw
    prior = sum(g_w.values()) / max(1, sum(g_n.values()))
    return g_n, g_w, t_n, t_w, prior


def strength(perk, wtype, stats):
    g_n, g_w, t_n, t_w, prior = stats
    s_global = (g_w[perk] + K_GLOBAL * prior) / (g_n[perk] + K_GLOBAL)
    return (t_w[wtype][perk] + K_TYPE * s_global) / (t_n[wtype][perk] + K_TYPE)


def column_values(w, col, recs, stats):
    """Value of each perk in a column, relative to that column's options."""
    s = {p: strength(p, w["wtype"], stats) for p in col}
    # Reference: the average general strength of the perks the sheet endorses on this weapon.
    s_ref = max(sum(s[p] for p in recs) / len(recs), max((s[p] for p in col if p not in recs), default=0), 1e-6)
    vals = {}
    for p in col:
        if p in recs:
            vals[p] = LISTED[min(recs.index(p), len(LISTED) - 1)]
        else:
            # An unlisted perk as generally strong as an endorsed one approaches the cap.
            vals[p] = UNLISTED_CAP * min(1.0, s[p] / s_ref) ** GAMMA
    return vals, s


def pmean(a, b, p=P):
    if p == 0:
        return (a * b) ** 0.5
    return ((a ** p + b ** p) / 2) ** (1 / p)


def score(w, v3, v4, opts3, opts4, barrel, mag, p=P):
    t3 = max(v3[x] for x in opts3)
    t4 = max(v4[x] for x in opts4)
    extras = 0.9 + 0.05 * (barrel in w["rb"]) + 0.05 * (mag in w["rm"])
    return 100 * pmean(t3, t4, p) * extras


# ---------------------------------------------------------------- precompute per-weapon values (LOO)
VALS = {}
for mode, db in DBS.items():
    full = tally(db)
    VALS[mode] = {}
    for key, w in db.items():
        st = tally(db, exclude=key)  # strength learned without this weapon
        v3, s3 = column_values(w, w["c3"], w["r3"], st)
        v4, s4 = column_values(w, w["c4"], w["r4"], st)
        VALS[mode][key] = (v3, v4, s3, s4)
