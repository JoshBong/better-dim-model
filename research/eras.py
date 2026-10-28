"""Backtest of the historical (curators-only) era models, research/era_data.py + model.build_era.

For each era e > 0 and mode: the curator lists OF that era are split into 5 folds by source title. For each fold,
the era model is built from every list of era e and older EXCEPT the held-out fold (votes only, no sheet) and
scored on the held-out lists' endorsed trait pairs, gun by gun (AUC = chance an endorsed pair outscores a
non-endorsed one on the same gun). Two baselines on the same held-out groups: the current full model (sheet +
all votes, i.e. hindsight) and a flat score (AUC 0.5 by construction, omitted).

Usage: python eras.py            (takes a few minutes)
"""
import json
import os
import sys
from collections import defaultdict
from itertools import product

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
from better_dim import model as M  # noqa: E402
import era_data  # noqa: E402

pools, ballots, manifest = era_data.load_inputs()
hash_name = {w["hash"]: M.norm(w["name"]) for w in pools["weapons"]}
first = era_data.first_era(pools, ballots, manifest)
sheets = {m: list(json.load(open(f"{era_data.DATA}/dim-aegis-overlay/data/{m}-database.json"))["weapons"].values()) for m in ("pve", "pvp")}


def endorsed(mode, gunmap, subset):
    groups = defaultdict(set)
    for b in subset:
        g = gunmap.get(hash_name.get(b["item"]))
        if b["mode"] != mode or not g:
            continue
        a = [p for p, hs in g.c3.items() if set(hs) & set(b["perks"])]
        c = [p for p, hs in g.c4.items() if set(hs) & set(b["perks"])]
        for x in a:
            for y in c:
                groups[(b["source"], M.norm(g.name))].add((x, y))
    return groups


def auc_for(groups, gunmap, scorer):
    a = []
    for (src, name), end in groups.items():
        g = gunmap[name]
        pos, neg = [], []
        for x, y in product(g.c3, g.c4):
            if x == y:
                continue
            (pos if (x, y) in end else neg).append(scorer(g, x, y))
        if pos and neg:
            a.append(sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg)))
    return (round(sum(a) / len(a), 3) if a else None), len(a)


def frozen_scorer(f, mode):
    m = f["modes"][mode]
    prm, vp = f["params"][mode], f["vote_p"]

    def s(g, x, y):
        e = m["guns"].get(str(g.hash))
        if not e:
            return 0.0
        hx, hy = g.c3[x][0], g.c4[y][0]
        return M.pmean(e["c3"][str(hx)], e["c4"][str(hy)], prm["p"]) + prm["mu"] * M.pmean(
            m["votes"].get(str(hx), m["vote_prior"]), m["votes"].get(str(hy), m["vote_prior"]), vp)
    return s


# hindsight baseline: today's full model, all ballots
current = M.build("current", pools, sheets, {}, ballots)
print("era  mode  era-model AUC (n)   | hindsight full-model AUC (n)   | lists  weapons")
for era in era_data.ERAS[1:]:
    e = era["index"]
    avail = era_data.available_in(e, first)
    for mode in ("pve", "pvp"):
        sources = sorted({b["source"] for b in ballots if b["era"] == e and b["mode"] == mode})
        if len(sources) < 2:
            print(f"{e:>3}  {mode}  no lists")
            continue
        folds = [sources[i::5] for i in range(5)]
        aucs, ns, base, bn = [], 0, [], 0
        for held in folds:
            if not held:
                continue
            train = [b for b in ballots if b["source"] not in held]
            f = M.build_era(era, pools, train, available=avail)
            gunmap = {}
            for w in pools["weapons"]:
                n = M.norm(w["name"])
                if n in avail and n not in gunmap:
                    g = M._pool_gun(w)
                    if g:
                        gunmap[n] = g
            test = [b for b in ballots if b["source"] in held and b["era"] == e and b["mode"] == mode]
            groups = endorsed(mode, gunmap, test)
            a, n = auc_for(groups, gunmap, frozen_scorer(f, mode))
            b_, m_ = auc_for(groups, gunmap, frozen_scorer(current, mode))
            if a is not None:
                aucs.append(a * n); ns += n
            if b_ is not None:
                base.append(b_ * m_); bn += m_
        era_auc = round(sum(aucs) / ns, 3) if ns else None
        base_auc = round(sum(base) / bn, 3) if bn else None
        print(f"{e:>3}  {mode}  {str(era_auc):>8} ({ns:>4})   | {str(base_auc):>8} ({bn:>4})            | {len(sources):>3}    {len(avail)}")
