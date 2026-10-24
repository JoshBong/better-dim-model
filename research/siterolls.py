import os
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("BD_DATA", os.path.join(HERE, "data"))
exec(open(os.path.join(HERE, "gearscore_v2.py")).read())
from common import norm
def find(mode, nm):
    return next(k for k, w in DBS[mode].items() if w["name"].lower() == nm.lower())
def sc(mode, nm, a, b):
    k = find(mode, nm); w = DBS[mode][k]; v3, v4, _, _ = VALS[mode][k]
    a, b = norm(a), norm(b)
    if a in v4 and b in v3: a, b = b, a
    allp = sorted(100 * pmean(v3[x], v4[y]) for x in v3 for y in v4)
    s = 100 * pmean(v3[a], v4[b])
    pct = sum(x < s for x in allp) / len(allp)
    return f"{s:5.1f}  (beats {pct:.0%} of the {len(allp)} possible trait pairs)"
CASES = [
 ("pve","Cusp Sempiternal","reciprocity","destabilizing rounds","blueberries PvE"),
 ("pve","Cusp Sempiternal","reciprocity","master of arms","blueberries PvE alt"),
 ("pve","Cusp Sempiternal","attrition orbs","destabilizing rounds","blueberries PvE alt"),
 ("pve","Found Verdict","pugilist","one two punch","blueberries PvE (Feb 2025)"),
 ("pvp","Found Verdict","slideshot","opening shot","blueberries PvP (Feb 2025)"),
 ("pve","Igneous Hammer","firefly","incandescent","blueberries PvE (Jun 2026)"),
 ("pve","Igneous Hammer","heal clip","frenzy","blueberries PvE alt"),
 ("pve","Igneous Hammer","firefly","desperate measures","blueberries PvE 'also good'"),
 ("pvp","Igneous Hammer","rapid hit","opening shot","blueberries PvP"),
 ("pvp","Igneous Hammer","slideshot","precision instrument","blueberries PvP"),
 ("pvp","Igneous Hammer","moving target","adagio","blueberries PvP 'also good'"),
 ("pve","Fatebringer","explosive payload","frenzy","blueberries PvE (Feb 2025)"),
 ("pve","Fatebringer","explosive payload","firefly","blueberries PvE alt"),
 ("pvp","Fatebringer","opening shot","eye of the storm","blueberries PvP"),
 ("pvp","Fatebringer","explosive payload","magnificent howl","blueberries PvP alt"),
 ("pve","Hezen Vengeance","envious arsenal","bait and switch","esports.gg PvE (undated)"),
 ("pve","Hezen Vengeance","auto loading holster","explosive light","esports.gg PvE alt"),
 ("pvp","Hezen Vengeance","cluster bomb","vorpal weapon","esports.gg PvP"),
]
for mode, nm, a, b, src in CASES:
    try:
        print(f"{nm:17s} {mode} {a} + {b:22s} [{src}]: {sc(mode, nm, a, b)}")
    except Exception as e:
        print(nm, mode, a, b, "ERR", e)
