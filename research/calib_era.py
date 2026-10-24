import os
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("BD_DATA", os.path.join(HERE, "data"))
exec(open(os.path.join(HERE, "era_backtest.py")).read().split("CUR = ")[0])
POST_EOF = ("1 ", "2 ", "3 ")
for mode in ("pve", "pvp"):
    cur, rest, n = [], [], 0
    for (era, m, k), endorsed in eg.items():
        if m != mode or not era.startswith(POST_EOF):
            continue
        n += 1
        v3, v4, _, _ = VALS[mode][k]
        for a in v3:
            for b in v4:
                (cur if (a, b) in endorsed else rest).append(100 * pmean(v3[a], v4[b]))
    if not cur:
        continue
    cur.sort(); rest.sort()
    q = lambda v, f: v[int(f * (len(v) - 1))]
    print(f"{mode} (post-Edge of Fate sources only, {n} weapon lists): curated median {q(cur,.5):.0f}, non-curated median {q(rest,.5):.0f}")
    for t in (50, 60, 65, 70, 75):
        print(f"   keep >= {t}: catches {sum(x >= t for x in cur)/len(cur):.0%} of curated, flags {sum(x >= t for x in rest)/len(rest):.0%} of others")
