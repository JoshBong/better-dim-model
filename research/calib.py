import os
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("BD_DATA", os.path.join(HERE, "data"))
exec(open(os.path.join(HERE, "tune.py")).read().split("GRID = ")[0])
for mode in ("pve", "pvp"):
    cur, rest = [], []
    for (sp, m, k), endorsed in groups.items():
        if m != mode or sp == "train":
            continue
        v3, v4, _, _ = VALS[mode][k]
        for a in v3:
            for b in v4:
                (cur if (a, b) in endorsed else rest).append(100 * pmean(v3[a], v4[b]))
    cur.sort(); rest.sort()
    q = lambda v, f: v[int(f * (len(v) - 1))]
    print(f"{mode}: curated pairs p25 {q(cur,.25):.0f} / median {q(cur,.5):.0f} / p75 {q(cur,.75):.0f}; non-curated median {q(rest,.5):.0f}, p90 {q(rest,.9):.0f}")
    for t in (50, 55, 60, 65, 70, 75):
        tp = sum(x >= t for x in cur) / len(cur); fp = sum(x >= t for x in rest) / len(rest)
        print(f"   keep >= {t}: catches {tp:.0%} of curated, flags {fp:.0%} of non-curated")
