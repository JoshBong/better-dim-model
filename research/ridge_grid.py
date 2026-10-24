"""Full 2-ball grid (per-perk ball tP x per-perk-per-type ball tT), with a validation split that respects
the Edge of Fate meta shift: fit on pre-EoF lists (eras 4-7), pick (tP, tT) on Edge of Fate / Ash & Iron
lists (era 3), test once on Renegades + Monument of Triumph lists (eras 1-2).
PvP has no era-3 lists, so PvP picks on era 2 and tests on era 1 (tiny sample, flagged).
"""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("BD_DATA", os.path.join(HERE, "data"))
import json
import math
from itertools import product

exec(open(os.path.join(HERE, "ridge.py")).read().split("T_P = [")[0])

TP = [0.0, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0]
TT = [0.0, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0]
pre_eof = by_era(("4", "5", "6", "7"))
split = {
    "pve": (by_era(("3",)), by_era(("1", "2"))),
    "pvp": (by_era(("2",)), by_era(("1",))),
}
out = {}
for mode in ("pve", "pvp"):
    val_set, tst_set = split[mode]
    grid = {}
    for tP, tT in product(TP, TT):
        (a, n), _, _ = run(mode, pre_eof, val_set, (tP, tT, 1.0))
        grid[(tP, tT)] = a
    best = max(grid, key=grid.get)
    test_best = run(mode, pre_eof, tst_set, (*best, 1.0))[0]
    test_none = run(mode, pre_eof, tst_set, (0.0, 0.0, 1.0))[0]
    st_pre = learn(pre_eof)
    f = evaluate(tst_set, st_pre, 0, 0)[mode]
    v = evaluate(tst_set, st_pre, 1.0, 0)[mode]
    out[mode] = dict(grid={f"{k[0]},{k[1]}": round(x, 4) for k, x in grid.items()}, best=best,
                     val_n=run(mode, pre_eof, val_set, (0.0, 0.0, 1.0))[0][1])
    print(f"\n=== {mode}: validation AUC grid (rows tP, cols tT), n={out[mode]['val_n']} lists ===")
    print("tP\\tT " + " ".join(f"{t:>6}" for t in TT))
    for tP in TP:
        print(f"{tP:>5} " + " ".join(f"{grid[(tP, tT)]:6.3f}" for tT in TT))
    print(f"picked tP={best[0]} tT={best[1]} (val {grid[best]:.3f})")
    print(f"TEST ({test_best[1]} lists): formula {f[0]:.3f} | +votes(count) {v[0]:.3f} | ridge no balls {test_none[0]:.3f} | ridge picked {test_best[0]:.3f}")
json.dump(out, open(os.path.join(HERE, "ridge_grid.json"), "w"), default=list)
