import os
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("BD_DATA", os.path.join(HERE, "data"))
import sys, json
from collections import Counter
src = open("gearscore.py").read().split("db_e, st_e = build(pve)")[0]
g = {}; exec(compile(src, "gs", "exec"), g)
db_e,_ = g["build"](g["pve"]); db_p,_ = g["build"](g["pvp"])
out = {}
for lab, db in (("pve", db_e), ("pvp", db_p)):
    c = Counter()
    for w in db.values():
        for _ in range(300):
            o3,o4,b,m = g["sample_roll"](w)
            c[min(int(g["score"](w,o3,o4,b,m)//10)*10, 90)] += 1
    t = sum(c.values()); out[lab] = [round(100*c[k]/t,1) for k in range(0,100,10)]
print(json.dumps(out))
