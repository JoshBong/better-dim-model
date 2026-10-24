import os
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("BD_DATA", os.path.join(HERE, "data"))
import sys, runpy
from collections import Counter
sys.argv = ["gearscore.py", sys.argv[1]]
import builtins
# reuse functions without rerunning prints: exec module body up to definitions
src = open("gearscore.py").read().split("db_e, st_e = build(pve)")[0]
g = {}
exec(compile(src, "gearscore", "exec"), g)
build, score, sample_roll, band, norm, split_list = g["build"], g["score"], g["sample_roll"], g["band"], g["norm"], g["split_list"]
pve, pvp, by_name = g["pve"], g["pvp"], g["by_name"]

# 1) why perks fail to match
miss = Counter()
for sheet in (pve, pvp):
    for w in sheet.values():
        m = by_name.get(norm(w["name"]))
        if not m: continue
        cols = {norm(x) for c in m["perkColumns"] for x in c}
        for p in split_list(w.get("perk1","")) + split_list(w.get("perk2","")):
            if p not in cols: miss[p] += 1
print("top unmatched sheet perk names:", miss.most_common(15))
nm = Counter()
for w in pvp.values():
    if not by_name.get(norm(w["name"])): nm[w["name"]] += 1
print("sample PvP names with no manifest match:", list(nm)[:8])

# 2) gentler decay + tier gating + union keep rate
db_e, _ = build(pve); db_p, _ = build(pvp)
TIERW = {"S":1.0,"A":1.0,"B":0.95,"C":0.85,"D":0.7,"E":0.5,"F":0.3}
for decay in ([1.0,0.8,0.6,0.5,0.45],[1.0,0.9,0.8,0.75,0.7]):
    g["RANK_VALUES"][:] = decay
    for label, db in (("PvE",db_e),("PvP",db_p)):
        keep_by_tier, bands, gated = Counter(), Counter(), Counter()
        for w in db.values():
            for _ in range(300):
                o3,o4,b,m = sample_roll(w)
                s = score(w,o3,o4,b,m)
                bands[band(s)] += 1
                if s >= 80: keep_by_tier[w["tier"] or "?"] += 1
                gated[band(s*TIERW.get(w["tier"],0.8))] += 1
        t = sum(bands.values()); k = sum(keep_by_tier.values())
        low = sum(v for kk,v in keep_by_tier.items() if kk in "DEF")
        print(f"decay={decay[:3]} {label}: bands {{{', '.join(f'{x}:{v/t:.1%}' for x,v in bands.items())}}} | keeps from D/E/F-tier weapons {low/k:.0%} | tier-gated keep {gated['keep']/t:.1%}")
# union keep rate on shared weapons
both=[k for k in set(db_e)&set(db_p) if db_e[k]["c3"]==db_p[k]["c3"]]
u=e=p=n=0
for k in both:
    for _ in range(300):
        o3,o4,b,m = sample_roll(db_e[k])
        a=score(db_e[k],o3,o4,b,m)>=80; c=score(db_p[k],o3,o4,b,m)>=80
        e+=a; p+=c; u+=a or c; n+=1
print(f"shared weapons: keep PvE {e/n:.1%}, PvP {p/n:.1%}, either {u/n:.1%}")
