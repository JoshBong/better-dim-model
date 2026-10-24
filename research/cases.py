import os
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("BD_DATA", os.path.join(HERE, "data"))
import sys
exec(open(os.path.join(HERE, "gearscore_v2.py")).read())
names = sys.argv[1].split("|")
mode = sys.argv[2]
for nm in names:
    hits = [k for k, w in DBS[mode].items() if w["name"].lower().startswith(nm.lower())]
    for k in hits[:1]:
        w = DBS[mode][k]; v3, v4, s3, s4 = VALS[mode][k]
        print(f"\n### {w['name']} [{w['wtype']}, {mode} tier {w['tier']}]  notes: {w['notes'][:140]!r}")
        for lab, v, s in (("col3", v3, s3), ("col4", v4, s4)):
            print(f"  {lab}: " + ", ".join(f"{p}={v[p]:.2f}" for p in sorted(v, key=lambda p: -v[p])))
        r3, r4 = w["r3"], w["r4"]
        best3 = max(v3, key=v3.get); best4 = max(v4, key=v4.get)
        u3 = sorted((p for p in v3 if p not in r3), key=lambda p: -v3[p]); u4 = sorted((p for p in v4 if p not in r4), key=lambda p: -v4[p])
        rb = w["rb"][0] if w["rb"] else ""; rm = w["rm"][0] if w["rm"] else ""
        rolls = [(best3, best4, "god"), (r3[-1], r4[-1], "lowest listed both"),
                 (best3, u4[0], "#1 + best unlisted"), (best3, u4[-1], "#1 + worst unlisted"),
                 (u3[0], u4[0], "best unlisted both"), (u3[-1], u4[-1], "worst both")]
        for a, b, tag in rolls:
            print(f"    {tag:22s} {a} + {b}: {score(w, v3, v4, [a], [b], rb, rm):.0f}")
