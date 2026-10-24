"""Does a learned pair-synergy term beat the v2 formula?

Models (all ranked by AUC: curator-endorsed trait pairs vs every other pair on that gun):
  A  v2 formula (baseline)
  B  A + mu * curator marginal (how often curators endorse each perk on its own)   <- control
  C  B + lam * synergy(a, b)  (shrunk log-lift: are a and b endorsed TOGETHER more than chance?)

Protocol (no peeking at the test set):
  learn stats on eras 5-7 (2020-2024) -> pick mu/lam on era 4 (Final Shape episodes)
  then relearn stats on eras 4-7 and evaluate on eras 1-3 (post-Edge-of-Fate) and on JAT.
Also reports test AUC on guns that never appear in the training lists (pure generalization).
"""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("BD_DATA", os.path.join(HERE, "data"))
import math
import sys
from collections import Counter, defaultdict
from itertools import product

SP = HERE
exec(open(f"{SP}/era_backtest.py").read().split("CUR = ")[0])

K_M, K_S = 10.0, 10.0  # shrinkage strengths


def learn(groups_):
    """Per-mode perk marginals and pair co-endorsement counts from curator lists."""
    stats = {}
    for mode in ("pve", "pvp"):
        n_a, e_a, n_ab, e_ab = Counter(), Counter(), Counter(), Counter()
        for (era, m, k), endorsed in groups_:
            if m != mode:
                continue
            w = DBS[mode][k]
            end_perks = {p for pair in endorsed for p in pair}
            for p in set(w["c3"]) | set(w["c4"]):
                n_a[p] += 1
                e_a[p] += p in end_perks
            for a, b in product(w["c3"], w["c4"]):
                key = frozenset((a, b))
                n_ab[key] += 1
                e_ab[key] += (a, b) in endorsed
        prior = sum(e_a.values()) / max(1, sum(n_a.values()))
        marg = {p: (e_a[p] + K_M * prior) / (n_a[p] + K_M) for p in n_a}
        # Pair endorsement rate given both perks are endorsement-worthy, vs independence.
        pair_prior = sum(e_ab.values()) / max(1, sum(n_ab.values()))
        stats[mode] = dict(marg=marg, prior=prior, n_ab=n_ab, e_ab=e_ab, pair_prior=pair_prior)
    return stats


def synergy(st, a, b):
    ma, mb = st["marg"].get(a, st["prior"]), st["marg"].get(b, st["prior"])
    # Expected pair rate if curators picked each column independently: proportional to ma*mb.
    expected = st["pair_prior"] * (ma * mb) / max(st["prior"] ** 2, 1e-9)
    expected = min(max(expected, 1e-4), 0.999)
    key = frozenset((a, b))
    p = (st["e_ab"][key] + K_S * expected) / (st["n_ab"][key] + K_S)
    return math.log(p / expected)


def evaluate(groups_eval, st, mu, lam, only_cold=None):
    res = defaultdict(list)
    for (era, mode, k), endorsed in groups_eval:
        if only_cold is not None and (mode, k) in only_cold:
            continue
        w = DBS[mode][k]
        v3, v4, _, _ = VALS[mode][k]
        s = st[mode]
        pos, neg = [], []
        for a, b in product(w["c3"], w["c4"]):
            score = pmean(v3[a], v4[b])
            if mu:
                score += mu * pmean(s["marg"].get(a, s["prior"]), s["marg"].get(b, s["prior"]))
            if lam:
                score += lam * synergy(s, a, b)
            (pos if (a, b) in endorsed else neg).append(score)
        if pos and neg:
            res[mode].append(auc(pos, neg))
    return {m: (sum(v) / len(v), len(v)) for m, v in res.items()}


items = list(eg.items())
by_era = lambda prefixes: [(g, e) for g, e in items if g[0].startswith(prefixes)]
learn_set, valid_set = by_era(("5", "6", "7")), by_era(("4",))
train_full, test_set, jat_set = by_era(("4", "5", "6", "7")), by_era(("1", "2", "3")), by_era(("0",))

# 1) pick mu, lam on the validation era
st = learn([(g, e) for g, e in learn_set])
grid = [(mu, lam) for mu in (0, 0.25, 0.5, 1.0) for lam in (0, 0.02, 0.05, 0.1, 0.2)]
val = {g: evaluate(valid_set, st, *g) for g in grid}
best = {m: max(grid, key=lambda g: val[g][m][0]) for m in ("pve", "pvp")}
best_mu_only = {m: max([g for g in grid if g[1] == 0], key=lambda g: val[g][m][0]) for m in ("pve", "pvp")}
print("validation (era 4) AUC:")
for m in ("pve", "pvp"):
    print(f"  {m}: A {val[(0, 0)][m][0]:.3f} | B best mu={best_mu_only[m][0]} {val[best_mu_only[m]][m][0]:.3f}"
          f" | C best mu={best[m][0]} lam={best[m][1]} {val[best[m]][m][0]:.3f}")

# 2) relearn on all older eras, evaluate on held-out recent lists
st = learn(train_full)
train_guns = {(g[1], g[2]) for g, _ in train_full}
print("\ntest AUC (stats learned on 2020-mid 2025, params picked on era 4):")
for name, ds in (("post-Edge-of-Fate curators", test_set), ("JAT (Aegis-built, Dec 2025)", jat_set)):
    for cold in (None, train_guns):
        tag = "all guns" if cold is None else "guns unseen in training"
        for m in ("pve", "pvp"):
            a = evaluate(ds, st, 0, 0, cold).get(m)
            b = evaluate(ds, st, best_mu_only[m][0], 0, cold).get(m)
            c = evaluate(ds, st, *best[m], cold).get(m)
            if a:
                print(f"  {name:30s} {tag:24s} {m}: A {a[0]:.3f}  B {b[0]:.3f}  C {c[0]:.3f}   (n={a[1]})")

# 3) what synergy actually learned: strongest positive pairs with real support
print("\nstrongest learned synergies (>= 15 co-offers):")
for m in ("pve", "pvp"):
    s = st[m]
    top = sorted(((synergy(s, *tuple(k) if len(k) == 2 else (next(iter(k)),) * 2), k) for k in s["n_ab"] if s["n_ab"][k] >= 15),
                 key=lambda x: -x[0])[:6]
    print(f"  {m}: " + "; ".join(f"{' + '.join(sorted(k))} ({v:+.2f})" for v, k in top))
