import os
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("BD_DATA", os.path.join(HERE, "data"))
import sys
from collections import Counter, defaultdict

exec(open(os.path.join(HERE, "gearscore_v2.py")).read())
P_OVERRIDE = float(sys.argv[1]) if len(sys.argv) > 1 else P


def auc(pos, neg):
    if not pos or not neg:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


# A. Does learned perk strength (from OTHER weapons) predict what the sheet picks on THIS weapon?
print("A. leave-one-weapon-out: does general perk strength predict this weapon's sheet picks?")
for mode, db in DBS.items():
    aucs, top1, by_type = [], 0, defaultdict(list)
    cols = 0
    for key, w in db.items():
        v3, v4, s3, s4 = VALS[mode][key]
        for col, recs, s in ((w["c3"], w["r3"], s3), (w["c4"], w["r4"], s4)):
            a = auc([s[p] for p in col if p in recs], [s[p] for p in col if p not in recs])
            if a is None:
                continue
            aucs.append(a)
            by_type[w["wtype"]].append(a)
            top1 += max(col, key=lambda p: s[p]) in recs
            cols += 1
    worst = sorted(((sum(v) / len(v), t, len(v)) for t, v in by_type.items() if len(v) >= 20))[:3]
    print(f"  {mode}: mean AUC {sum(aucs) / len(aucs):.3f} over {cols} columns | strongest-perk-is-listed {top1 / cols:.1%}"
          f" | weakest types {[(t, round(a, 2), n) for a, t, n in worst]}")

# B. Mechanics check: hand-labeled perk categories (from Clarity descriptions) vs learned strength
CATS = {
    "damage buff": ["kill clip", "rampage", "frenzy", "surrounded", "bait and switch", "golden tricorn",
                    "one for all", "multikill clip", "swashbuckler", "adrenaline junkie", "target lock",
                    "vorpal weapon", "precision instrument"],
    "add-clear/chain": ["incandescent", "destabilizing rounds", "voltshot", "firefly", "dragonfly",
                        "kinetic tremors", "chain reaction", "explosive payload", "hatchling", "headstone", "tear"],
    "ammo/uptime": ["reconstruction", "rewind rounds", "envious arsenal", "subsistence", "shoot to loot",
                    "demolitionist", "auto loading holster", "overflow"],
    "aim/handling/range stats": ["snapshot sights", "moving target", "eye of the storm", "perpetual motion",
                                 "opening shot", "lone wolf", "keep away", "zen moment", "rangefinder",
                                 "encore", "quickdraw", "headseeker"],
}
print("\nB. mean learned strength by perk mechanic (higher = sheets pick it more often when offered)")
for mode, db in DBS.items():
    st = tally(db)
    row = []
    for cat, perks in CATS.items():
        vals = [st[1][p] / st[0][p] for p in perks if st[0][p] >= 5]
        row.append(f"{cat}: {sum(vals) / len(vals):.2f}")
    print(f"  {mode}: " + " | ".join(row))

# C. Distribution of single-perk-per-column drops, and 2-per-column drops
def sim(mode, per_col=1, n=200, p=P_OVERRIDE):
    out = []
    for key, w in DBS[mode].items():
        v3, v4, _, _ = VALS[mode][key]
        for _ in range(n):
            o3 = random.sample(w["c3"], min(per_col, len(w["c3"])))
            o4 = random.sample(w["c4"], min(per_col, len(w["c4"])))
            b = random.choice(w["barrels"]) if w["barrels"] else ""
            m = random.choice(w["mags"]) if w["mags"] else ""
            out.append(score(w, v3, v4, o3, o4, b, m, p))
    return out


print(f"\nC. score distribution (p={P_OVERRIDE})")
for mode in DBS:
    for pc in (1, 2):
        s = sim(mode, pc)
        h = Counter(min(int(x // 10) * 10, 90) for x in s)
        t = len(s)
        bands = [("90+", sum(x >= 90 for x in s)), ("75-90", sum(75 <= x < 90 for x in s)),
                 ("55-75", sum(55 <= x < 75 for x in s)), ("<55", sum(x < 55 for x in s))]
        print(f"  {mode} {pc}/col: " + " ".join(f"{k}:{v / t:.1%}" for k, v in bands)
              + " | deciles " + " ".join(f"{k}:{h[k] / t:.0%}" for k in range(0, 100, 10)))
