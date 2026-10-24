import os
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("BD_DATA", os.path.join(HERE, "data"))
# Can the model score guns the sheet doesn't list? Two checks:
#  A) sheet guns scored as if unlisted (LOO strength only, no listed bonus) vs their normal score
#  B) truly off-sheet pool guns (strength from all sheet guns) — the real population
import json, sys
from collections import defaultdict, Counter
from itertools import product
sys.path.insert(0,os.path.join(HERE, ".."))
from better_dim import model as M, curators
pools=json.load(open(DATA + '/ext/pools.json'))
hash_name={w['hash']:M.norm(w['name']) for w in pools['weapons']}
sheets={m: list(json.load(open(DATA + f'/dim-aegis-overlay/data/{m}-database.json'))['weapons'].values()) for m in ('pve','pvp')}
ballots=curators.parse(open(DATA + '/ext/wl/voltron.txt',errors='ignore').read())
train=[b for b in ballots if b['era']>=3]

def stats(guns):
    distinct={}
    for g in guns.values(): distinct.setdefault((M.norm(g.name),tuple(sorted(g.c3)),tuple(sorted(g.c4))),g)
    g_n,g_w,t_n,t_w=Counter(),Counter(),defaultdict(Counter),defaultdict(Counter)
    for g in distinct.values():
        for p,pw in M._contributions(g):
            g_n[p]+=1;g_w[p]+=pw;t_n[g.wtype][p]+=1;t_w[g.wtype][p]+=pw
    return g_n,g_w,t_n,t_w

def estimate(g, st, mode, own=None):
    """unlisted formula for every perk; own = this gun's contributions to subtract (LOO)"""
    g_n,g_w,t_n,t_w=st; prm=M.PARAMS[mode]
    own_n,own_w=Counter(),Counter()
    if own:
        for p,pw in M._contributions(own): own_n[p]+=1; own_w[p]+=pw
    tn_all,tw_all=sum(g_n.values()),sum(g_w.values())
    prior=(tw_all-sum(own_w.values()))/max(1,tn_all-sum(own_n.values()))
    def s(p):
        gs=(g_w[p]-own_w[p]+M.K_GLOBAL*prior)/(g_n[p]-own_n[p]+M.K_GLOBAL)
        return (t_w[g.wtype][p]-own_w[p]+M.K_TYPE*gs)/(t_n[g.wtype][p]-own_n[p]+M.K_TYPE)
    out=[]
    for col in (g.c3,g.c4):
        sv={p:s(p) for p in col}; ref=max(max(sv.values()),1e-6)
        out.append({p:prm['cap']*min(1,sv[p]/ref)**prm['gamma'] for p in col})
    return out

def auc_for(groups, gunmap, scorer):
    a=[]
    for (era,name),end in groups.items():
        g=gunmap[name]; pos=[];neg=[]
        for x,y in product(g.c3,g.c4):
            if x==y: continue
            (pos if (x,y) in end else neg).append(scorer(g,x,y))
        if pos and neg: a.append(sum((p>n)+0.5*(p==n) for p in pos for n in neg)/(len(pos)*len(neg)))
    return (round(sum(a)/len(a),3) if a else None), len(a)

def endorsed(mode, gunmap, eras):
    groups=defaultdict(set)
    for b in ballots:
        g=gunmap.get(hash_name.get(b['item']))
        if b['mode']!=mode or b['era'] not in eras or not g: continue
        A=[p for p,hs in g.c3.items() if set(hs)&set(b['perks'])]; C=[p for p,hs in g.c4.items() if set(hs)&set(b['perks'])]
        for x in A:
            for y in C: groups[(b['era'],M.norm(g.name))].add((x,y))
    return groups

for mode,test_eras in (('pve',(0,1)),('pvp',(0,1,2))):
    prm=M.PARAMS[mode]
    guns=M.join(pools,sheets[mode]); M.rate(guns,mode); st=stats(guns)
    byname={M.norm(g.name):g for g in guns.values()}
    # off-sheet pool guns as Gun objects (no recs)
    off={}
    for w in pools['weapons']:
        n=M.norm(w['name'])
        if n in byname or n in off: continue
        c3,c4=M._named(w['c3']),M._named(w['c4'])
        if len(c3)<2 or len(c4)<2: continue
        off[n]=M.Gun(hash=w['hash'],name=w['name'],wtype=w['type'],c3=c3,c4=c4,barrels={},mags={},r3=[],r4=[],rb=[],rm=[],tier='')
    allguns={**{g.hash:g for g in guns.values()},**{g.hash:g for g in off.values()}}
    votes=M.learn_votes(train,allguns,mode,hash_name); pri=votes['__prior__']
    V=lambda p: votes.get(p,pri)
    vote_only=lambda g,x,y: M.pmean(V(x),V(y),M.VOTE_P)
    est_cache={}
    def est(g,x,y,loo,with_votes=True):
        k=(g.hash,loo)
        if k not in est_cache: est_cache[k]=estimate(g,st,mode,own=g if loo else None)
        v3,v4=est_cache[k]
        return M.pmean(v3[x],v4[y],prm['p'])+(prm['mu']*vote_only(g,x,y) if with_votes else 0)
    G=endorsed(mode,byname,test_eras)
    print(mode,'SHEET guns  full model      ',auc_for(G,byname,lambda g,x,y:M.raw_score(g,x,y,votes,mode)))
    print(mode,'SHEET guns  as-if-unlisted  ',auc_for(G,byname,lambda g,x,y:est(g,x,y,True)))
    print(mode,'SHEET guns  strength only   ',auc_for(G,byname,lambda g,x,y:est(g,x,y,True,False)))
    print(mode,'SHEET guns  votes only      ',auc_for(G,byname,vote_only))
    GO=endorsed(mode,off,test_eras)
    print(mode,'OFF-SHEET   estimate        ',auc_for(GO,off,lambda g,x,y:est(g,x,y,False)))
    print(mode,'OFF-SHEET   strength only   ',auc_for(GO,off,lambda g,x,y:est(g,x,y,False,False)))
    print(mode,'OFF-SHEET   votes only      ',auc_for(GO,off,vote_only))
    print(mode,'off-sheet legendary random-roll guns in pools:',len(off),' sheet:',len(byname))
