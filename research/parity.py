import os
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("BD_DATA", os.path.join(HERE, "data"))
import json, sys
from collections import defaultdict
from itertools import product
sys.path.insert(0,os.path.join(HERE, ".."))
from better_dim import model, curators
pools=json.load(open(DATA + '/ext/pools.json'))
hash_name={w['hash']:model.norm(w['name']) for w in pools['weapons']}
sheets={m: list(json.load(open(DATA + f'/dim-aegis-overlay/data/{m}-database.json'))['weapons'].values()) for m in ('pve','pvp')}
ballots=curators.parse(open(DATA + '/ext/wl/voltron.txt',errors='ignore').read())
train=[b for b in ballots if b['era']>=3]
for mode, test_eras in (('pve',(0,1)),('pvp',(0,1,2))):
    guns=model.join(pools, sheets[mode]); model.rate(guns, mode)
    byname={model.norm(g.name):g for g in guns.values()}
    tr=[dict(b, item=byname[hash_name[b['item']]].hash) for b in train if hash_name.get(b['item']) in byname]
    votes=model.learn_votes(train, guns, mode, hash_name)
    groups=defaultdict(set)
    for b in ballots:
        g=byname.get(hash_name.get(b['item']))
        if b['mode']!=mode or b['era'] not in test_eras or not g: continue
        a=[p for p,hs in g.c3.items() if set(hs)&set(b['perks'])]; c=[p for p,hs in g.c4.items() if set(hs)&set(b['perks'])]
        for x in a:
            for y in c: groups[(b['era'], model.norm(g.name))].add((x,y))
    for use_votes in (False, True):
        aucs=[]
        for (era,name),end in groups.items():
            g=byname[name]; pos=[];neg=[]
            for x,y in product(g.c3,g.c4):
                if x==y: continue
                s=model.raw_score(g,x,y,votes,mode) if use_votes else model.pmean(g.v3[x],g.v4[y],model.PARAMS[mode]['p'])
                (pos if (x,y) in end else neg).append(s)
            if pos and neg: aucs.append(sum((p>n)+0.5*(p==n) for p in pos for n in neg)/(len(pos)*len(neg)))
        print(mode, 'formula+votes' if use_votes else 'formula only', 'AUC', round(sum(aucs)/len(aucs),3), 'n', len(aucs))
