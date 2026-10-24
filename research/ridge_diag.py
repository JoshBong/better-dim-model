import os
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("BD_DATA", os.path.join(HERE, "data"))
exec(open(os.path.join(HERE, "ridge.py")).read().split("T_P = [")[0])
train_guns = {(g[1], g[2]) for g, _ in train_full}
print("DIAGNOSTIC ONLY (looks at the test set): post-EoF AUC by ball size, fit on eras 4-7")
for mode in ("pve", "pvp"):
    for decay in (1.0, 0.6):
        row = []
        for tP in (0.0, 0.25, 0.5, 1.0, 2.0, 8.0, 32.0):
            (a, n), _, _ = run(mode, train_full, test_set, (tP, 0.0, decay), train_guns)
            row.append(f"tP={tP}:{a:.3f}")
        print(f"  {mode} unseen guns, decay {decay}: " + "  ".join(row))
