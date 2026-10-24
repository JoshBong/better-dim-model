import os
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("BD_DATA", os.path.join(HERE, "data"))
exec(open(os.path.join(HERE, "synergy.py")).read().split("# 1) pick mu")[0])
st = learn(train_full)
for m in ("pve", "pvp"):
    s = st[m]
    print(m, "prior", round(s["prior"], 3))
    for p in ("incandescent", "firefly", "kill clip", "frenzy", "opening shot", "eye of the storm", "rampage", "snapshot sights"):
        print(f"   {p:18s} offered {sum(1 for (e,mm,k),_ in train_full if mm==m and p in set(DBS[m][k]['c3'])|set(DBS[m][k]['c4'])):4d}  vote {s['marg'].get(p, s['prior']):.2f}")
# worked example: Fatebringer PvE, EP + Frenzy vs EP + Firefly
k = next(k for k,w in DBS['pve'].items() if w['name']=='Fatebringer')
v3, v4, _, _ = VALS['pve'][k]; s = st['pve']
for a, b in (("explosive payload","firefly"),("explosive payload","frenzy"),("explosive payload","elemental honing")):
    base = pmean(v3[a], v4[b]); vote = pmean(s['marg'].get(a,s['prior']), s['marg'].get(b,s['prior']))
    print(f"Fatebringer {a}+{b}: formula {base:.2f} + 1.0*votes {vote:.2f} = {base+vote:.2f}")
