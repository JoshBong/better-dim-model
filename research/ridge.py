"""Ridge-constrained logistic model for pair endorsement, fit by projected gradient descent.

logit P(curator endorses pair a+b on gun g) =
    b0 + b1*v3[a] + b2*v4[b] + b3*pmean(v3[a], v4[b])          (formula terms, unconstrained)
  + theta_P[a] + theta_P[b]                                     (per-perk effect,   ||theta_P||^2 <= tP)
  + theta_T[a,type] + theta_T[b,type]                           (per-perk-per-type, ||theta_T||^2 <= tT)

Training rows are weighted by recency: decay ** (eras older than the newest training era).
Protocol: fit on eras 5-7, pick (tP, tT, decay) on era 4, refit on eras 4-7, test on eras 1-3 + JAT.
"""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("BD_DATA", os.path.join(HERE, "data"))
import math
import time
from itertools import product

import numpy as np
from scipy import sparse

SP = HERE
exec(open(f"{SP}/synergy.py").read().split("# 1) pick mu")[0])


def rows_for(groups_, mode, perk_idx, pt_idx, grow=False):
    """Build design matrices. Returns dense X (n,4), sparse P, sparse T, y, group ids, era numbers."""
    dense, pi, pj, ti, tj, y, gid, era = [], [], [], [], [], [], [], []
    for g_i, ((e, m, k), endorsed) in enumerate(groups_):
        if m != mode:
            continue
        w = DBS[mode][k]
        v3, v4, _, _ = VALS[mode][k]
        for a, b in product(w["c3"], w["c4"]):
            if a == b:
                continue
            for p in (a, b):
                if grow:
                    perk_idx.setdefault(p, len(perk_idx))
                    pt_idx.setdefault((p, w["wtype"]), len(pt_idx))
            dense.append((1.0, v3[a], v4[b], pmean(v3[a], v4[b])))
            pi.append([perk_idx.get(a, -1), perk_idx.get(b, -1)])
            ti.append([pt_idx.get((a, w["wtype"]), -1), pt_idx.get((b, w["wtype"]), -1)])
            y.append(1.0 if (a, b) in endorsed else 0.0)
            gid.append(g_i)
            era.append(int(e[0]))
    n = len(y)

    def onehot(idx_pairs, size):
        r, c = [], []
        for row, pair in enumerate(idx_pairs):
            for col in pair:
                if col >= 0:
                    r.append(row); c.append(col)
        return sparse.csr_matrix((np.ones(len(r)), (r, c)), shape=(n, max(size, 1)))

    return (np.array(dense), onehot(pi, len(perk_idx)), onehot(ti, len(pt_idx)),
            np.array(y), np.array(gid), np.array(era))


def project(theta, t):
    if math.isinf(t):
        return theta
    norm = np.linalg.norm(theta)
    r = math.sqrt(t)
    return theta if norm <= r else theta * (r / norm)


def fit(X, P, T, y, sw, tP, tT, iters=400, lr=0.5):
    beta = np.zeros(X.shape[1]); thP = np.zeros(P.shape[1]); thT = np.zeros(T.shape[1])
    sw = sw / sw.sum()
    # Adam on the weighted log-loss, then project each constrained block onto its ball.
    m = [np.zeros_like(beta), np.zeros_like(thP), np.zeros_like(thT)]
    v = [np.zeros_like(beta), np.zeros_like(thP), np.zeros_like(thT)]
    b1, b2, eps = 0.9, 0.999, 1e-8
    for it in range(1, iters + 1):
        z = X @ beta + P @ thP + T @ thT
        r = (1 / (1 + np.exp(-z)) - y) * sw
        grads = [X.T @ r, P.T @ r, T.T @ r]
        params = [beta, thP, thT]
        for i in range(3):
            m[i] = b1 * m[i] + (1 - b1) * grads[i]
            v[i] = b2 * v[i] + (1 - b2) * grads[i] ** 2
            params[i] -= lr * 0.05 * (m[i] / (1 - b1 ** it)) / (np.sqrt(v[i] / (1 - b2 ** it)) + eps)
        beta = params[0]
        thP = project(params[1], tP) if tP > 0 else np.zeros_like(thP)
        thT = project(params[2], tT) if tT > 0 else np.zeros_like(thT)
    return beta, thP, thT


def group_auc(score, y, gid, keep=None):
    out = []
    order = np.argsort(gid, kind="stable")
    gs, ss, ys = gid[order], score[order], y[order]
    bounds = np.flatnonzero(np.diff(gs)) + 1
    for s_, y_, g_ in zip(np.split(ss, bounds), np.split(ys, bounds), np.split(gs, bounds)):
        if keep is not None and not keep(g_[0]):
            continue
        pos, neg = s_[y_ == 1], s_[y_ == 0]
        if len(pos) and len(neg):
            out.append(auc(list(pos), list(neg)))
    return (sum(out) / len(out), len(out)) if out else (float("nan"), 0)


def run(mode, train_groups, eval_groups, params, cold_keys=None):
    tP, tT, decay = params
    perk_idx, pt_idx = {}, {}
    Xtr, Ptr, Ttr, ytr, _, era_tr = rows_for(train_groups, mode, perk_idx, pt_idx, grow=True)
    sw = decay ** (era_tr - era_tr.min())
    beta, thP, thT = fit(Xtr, Ptr, Ttr, ytr, sw.astype(float), tP, tT)
    Xev, Pev, Tev, yev, gid, _ = rows_for(eval_groups, mode, perk_idx, pt_idx)
    score = Xev @ beta + Pev @ thP + Tev @ thT
    keep = None
    if cold_keys is not None:
        keys = [g for g, _ in eval_groups]
        keep = lambda gi: (keys[gi][1], keys[gi][2]) not in cold_keys
    return group_auc(score, yev, gid, keep), float(thP @ thP), float(thT @ thT)


T_P = [0.0, 0.5, 2.0, 8.0, 32.0, math.inf]
T_T = [0.0, 0.5, 2.0, 8.0]
DECAY = [1.0, 0.6]

start = time.time()
results = {}
for mode in ("pve", "pvp"):
    print(f"\n=== {mode}: validation (fit eras 5-7, score era 4) ===")
    best, best_auc = None, -1
    for params in product(T_P, T_T, DECAY):
        (a, n), nP, nT = run(mode, learn_set, valid_set, params)
        if a > best_auc:
            best, best_auc = params, a
        if params[2] == 1.0 and params[1] in (0.0, 2.0):
            print(f"  tP={params[0]:<5} tT={params[1]:<4} decay={params[2]}: AUC {a:.3f}   (fitted ||thP||^2={nP:.1f}, ||thT||^2={nT:.1f})")
    print(f"  best: tP={best[0]} tT={best[1]} decay={best[2]} -> {best_auc:.3f}")
    results[mode] = best

train_guns = {(g[1], g[2]) for g, _ in train_full}
print("\n=== test (refit on eras 4-7 with chosen t, evaluate held-out) ===")
for mode in ("pve", "pvp"):
    for name, ds in (("post-EoF curators", test_set), ("JAT", jat_set)):
        for cold in (None, train_guns):
            r, _, _ = run(mode, train_full, ds, results[mode], cold)
            base, _, _ = run(mode, train_full, ds, (0.0, 0.0, 1.0), cold)  # = formula terms only, refit
            a_formula = evaluate(ds, st_full, 0, 0, cold)[mode][0] if (st_full := learn(train_full)) else None
            b_votes = evaluate(ds, st_full, 1.0, 0, cold)[mode][0]
            tag = "all guns" if cold is None else "unseen guns"
            print(f"  {mode} {name:18s} {tag:11s}: formula {a_formula:.3f} | +votes(count) {b_votes:.3f} | ridge {r[0]:.3f} (n={r[1]})")
print(f"\n({time.time() - start:.0f}s)")
