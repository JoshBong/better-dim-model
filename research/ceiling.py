import os
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("BD_DATA", os.path.join(HERE, "data"))
exec(open(os.path.join(HERE, "tune.py")).read().split("GRID = ")[0])
# How well does one curator source predict another? (upper bound on what any formula can hit)
for a, b in (("jat", "test"), ("train", "test"), ("jat", "train")):
    res = defaultdict(list)
    for (sp, mode, k), endorsed in groups.items():
        if sp != b or (a, mode, k) not in groups:
            continue
        other = groups[(a, mode, k)]
        w = DBS[mode][k]
        pairs = [(x, y) for x in w["c3"] for y in w["c4"]]
        pos = [1.0 if p in other else 0.0 for p in pairs if p in endorsed]
        neg = [1.0 if p in other else 0.0 for p in pairs if p not in endorsed]
        if pos and neg:
            res[mode].append(auc(pos, neg))
    print(f"{a:5s} predicting {b:5s}: " + ", ".join(f"{m} AUC {sum(v)/len(v):.3f} (n={len(v)})" for m, v in res.items()))
