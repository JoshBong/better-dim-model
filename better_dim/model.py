"""Per-patch gear-score model. Built once per Destiny patch, frozen, served to every extension.

Inputs (no Bungie API key anywhere):
  pools    weapon perk pools for this patch, read out of DIM's cached manifest by the extension
  sheets   Aegis (PvE) / Finnald (PvP) picks
  ballots  curator wishlist rolls (votes), tagged with mode and patch era

Per weapon and mode, a perk's value:
  listed by the sheet at rank i   -> max(1 - DECAY*i, 0.7)
  not listed                      -> CAP * min(1, s / s_ref) ** GAMMA
      s     = how often the sheets pick this perk when other guns of the same type offer it
              (leave-one-out, shrunk to the global rate, then to the overall prior)
      s_ref = max(mean s of the listed perks, strongest unlisted s)
A roll's raw score:
  pmean_P(best col-3 value, best col-4 value) + MU * pmean_0.5(vote col 3, vote col 4)
where vote = recency-weighted share of curator ballots endorsing the perk when offered.
Shown score = 100 * raw / (best raw on that gun) * (1 - 2*NUDGE + NUDGE per recommended barrel and mag),
so every gun's best roll is 100.
The sheet's weapon tier is reported separately.

Parameters were tuned per mode on an honest split (pick on Edge of Fate-era curator lists,
test on Renegades + Monument of Triumph lists): PvE AUC 0.805 -> 0.816, PvP 0.865 -> 0.894.
"""
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

PARAMS = {
    #       rank decay, unlisted cap, gamma, column power-mean p, curator-vote weight, vote recency per era
    "pve": dict(decay=0.20, cap=0.7, gamma=1.0, p=0.0, mu=1.0, recency=1.0),
    "pvp": dict(decay=0.15, cap=0.7, gamma=0.8, p=0.5, mu=1.0, recency=0.6),
}
LISTED_FLOOR = 0.7
K_GLOBAL, K_TYPE, K_VOTE = 6.0, 4.0, 10.0
RANK_PICK_WEIGHT = 0.15
VOTE_P = 0.5
NUDGE = 0.05  # per recommended barrel / mag; a gun whose sheet lists none is not penalised


def norm(s: str) -> str:
    s = s.lower().replace("enhanced", "").replace("’", "'")
    return re.sub(r"[^a-z0-9']+", " ", s).strip()


def split_list(s: str) -> list[str]:
    return [norm(x) for x in re.split(r"[\n/,]+", s or "") if x.strip()]


def pmean(a: float, b: float, p: float) -> float:
    if p == 0:
        return (max(a, 0) * max(b, 0)) ** 0.5
    return ((a ** p + b ** p) / 2) ** (1 / p)


@dataclass
class Gun:
    """One weapon definition from the patch's pools, joined to a sheet entry."""
    hash: int
    name: str
    wtype: str
    c3: dict[str, list[int]]          # perk name -> plug hashes (base + enhanced) in trait column 1
    c4: dict[str, list[int]]
    barrels: dict[str, list[int]]
    mags: dict[str, list[int]]
    r3: list[str] = field(default_factory=list)
    r4: list[str] = field(default_factory=list)
    rb: list[str] = field(default_factory=list)
    rm: list[str] = field(default_factory=list)
    tier: str = ""
    v3: dict[str, float] = field(default_factory=dict)
    v4: dict[str, float] = field(default_factory=dict)


def _named(entries) -> dict[str, list[int]]:
    out: dict[str, list[int]] = defaultdict(list)
    for h, name in entries:
        out[norm(name)].append(int(h))
    return dict(out)


def join(pools: dict, sheet: list[dict]) -> dict[int, Gun]:
    """Attach sheet entries to pool weapons by name. Reissues share a name but not a pool, so each
    sheet entry goes to the same-name weapons whose pool best covers its picks."""
    by_name: dict[str, list[dict]] = defaultdict(list)
    for w in pools["weapons"]:
        by_name[norm(w["name"])].append(w)
    guns: dict[int, Gun] = {}
    for entry in sheet:
        p1, p2 = split_list(entry.get("perk1", "")), split_list(entry.get("perk2", ""))
        if not p1 or not p2:
            continue
        base = norm(re.sub(r"\(.*?\)", "", entry["name"]))
        cands = by_name.get(norm(entry["name"])) or by_name.get(base) or []
        recs = p1 + p2

        def cover(w):
            pool = {norm(n) for _, n in w["c3"] + w["c4"]}
            return sum(r in pool for r in recs)

        if not cands:
            continue
        best = max(cover(w) for w in cands)
        for w in cands:
            if cover(w) != best or w["hash"] in guns:
                continue
            c3, c4 = _named(w["c3"]), _named(w["c4"])
            r3 = list(dict.fromkeys([p for p in p1 if p in c3] + [p for p in p2 if p in c3]))
            r4 = list(dict.fromkeys([p for p in p2 if p in c4] + [p for p in p1 if p in c4]))
            if not r3 or not r4:
                continue
            guns[w["hash"]] = Gun(
                hash=w["hash"], name=w["name"], wtype=w["type"], c3=c3, c4=c4,
                barrels=_named(w.get("barrels", [])), mags=_named(w.get("mags", [])),
                r3=r3, r4=r4, rb=split_list(entry.get("barrel", "")), rm=split_list(entry.get("mag", "")),
                tier=entry.get("tier", ""),
            )
    return guns


def _contributions(g: Gun):
    for col, recs in ((g.c3, g.r3), (g.c4, g.r4)):
        for p in col:
            yield p, ((1 - RANK_PICK_WEIGHT * recs.index(p)) if p in recs else 0.0)


def rate(guns: dict[int, Gun], mode: str) -> None:
    """Fill v3/v4 in place. Reissues with identical pools count once in the strength stats."""
    prm = PARAMS[mode]
    distinct: dict[tuple, Gun] = {}
    for g in guns.values():
        distinct.setdefault((norm(g.name), tuple(sorted(g.c3)), tuple(sorted(g.c4))), g)
    g_n, g_w = Counter(), Counter()
    t_n, t_w = defaultdict(Counter), defaultdict(Counter)
    for g in distinct.values():
        for p, pw in _contributions(g):
            g_n[p] += 1; g_w[p] += pw
            t_n[g.wtype][p] += 1; t_w[g.wtype][p] += pw
    total_n, total_w = sum(g_n.values()), sum(g_w.values())

    for g in guns.values():
        own_n, own_w = Counter(), Counter()
        for p, pw in _contributions(g):
            own_n[p] += 1; own_w[p] += pw
        prior = (total_w - sum(own_w.values())) / max(1, total_n - sum(own_n.values()))

        def strength(p):
            gn, gw = g_n[p] - own_n[p], g_w[p] - own_w[p]
            tn, tw = t_n[g.wtype][p] - own_n[p], t_w[g.wtype][p] - own_w[p]
            s_global = (gw + K_GLOBAL * prior) / (gn + K_GLOBAL)
            return (tw + K_TYPE * s_global) / (tn + K_TYPE)

        for col, recs, target in ((g.c3, g.r3, g.v3), (g.c4, g.r4, g.v4)):
            s = {p: strength(p) for p in col}
            s_ref = max(sum(s[p] for p in recs) / len(recs), max((s[p] for p in col if p not in recs), default=0), 1e-6)
            for p in col:
                if p in recs:
                    target[p] = max(1 - prm["decay"] * recs.index(p), LISTED_FLOOR)
                else:
                    target[p] = prm["cap"] * min(1.0, s[p] / s_ref) ** prm["gamma"]


def learn_votes(ballots: list[dict], guns_by_hash: dict[int, Gun], mode: str,
                hash_to_name: dict[int, str]) -> dict[str, float]:
    """Share of curator ballots that endorse a perk when the gun offers it, recency-weighted.

    ballot = {"mode", "era" (0 = newest), "item": item hash, "perks": [plug hashes in the endorsed roll]}
    All rolls for one gun within one patch era form one ballot (as in the tuning backtest), so a curator
    listing six variants of a roll doesn't count six times.
    """
    rec = PARAMS[mode]["recency"]
    eras = [b["era"] for b in ballots if b["mode"] == mode]
    newest = min(eras) if eras else 0
    # Route ballots by weapon name: curators often list a reissue's hash rather than the one rated here.
    gun_by_name = {norm(g.name): g for g in guns_by_hash.values()}
    endorsed: dict[tuple, set] = defaultdict(set)
    for b in ballots:
        g = gun_by_name.get(hash_to_name.get(b["item"], ""))
        if b["mode"] != mode or not g:
            continue
        names = {p for p, hs in {**g.c3, **g.c4}.items() if set(hs) & set(b["perks"])}
        endorsed[(b["era"], norm(g.name))] |= names
    n, e = Counter(), Counter()
    for (era, name), names in endorsed.items():
        if not names:
            continue
        w = rec ** (era - newest)
        g = gun_by_name[name]
        for p in set(g.c3) | set(g.c4):
            n[p] += w
            e[p] += w * (p in names)
    prior = sum(e.values()) / max(1e-9, sum(n.values()))
    votes = {p: (e[p] + K_VOTE * prior) / (n[p] + K_VOTE) for p in n}
    votes["__prior__"] = prior
    return votes


def raw_score(g: Gun, a: str, b: str, votes: dict[str, float], mode: str) -> float:
    prm = PARAMS[mode]
    prior = votes.get("__prior__", 0.0)
    return pmean(g.v3[a], g.v4[b], prm["p"]) + prm["mu"] * pmean(votes.get(a, prior), votes.get(b, prior), VOTE_P)


def freeze(patch: str, sheets_as_of: dict, modes: dict[str, tuple[dict[int, Gun], dict[str, float]]]) -> dict:
    """Serialize to the compact form the extension scores with, keyed by plug hash."""
    out = {"patch": patch, "sheets_as_of": sheets_as_of, "params": PARAMS, "vote_p": VOTE_P, "nudge": NUDGE,
           "modes": {}}
    for mode, (guns, votes) in modes.items():
        prior = votes.get("__prior__", 0.0)
        guns_out, vote_out = {}, {}
        for g in guns.values():
            best = max(raw_score(g, a, b, votes, mode) for a in g.c3 for b in g.c4 if a != b)
            guns_out[str(g.hash)] = {
                "name": g.name, "tier": g.tier, "best": round(best, 5),
                "c3": {str(h): round(v, 4) for p, v in g.v3.items() for h in g.c3[p]},
                "c4": {str(h): round(v, 4) for p, v in g.v4.items() for h in g.c4[p]},
                "rb": [h for n in g.rb for h in g.barrels.get(n, [])],
                "rm": [h for n in g.rm for h in g.mags.get(n, [])],
            }
            for p, hs in {**g.c3, **g.c4}.items():
                for h in hs:
                    vote_out[str(h)] = round(votes.get(p, prior), 4)
        out["modes"][mode] = {"guns": guns_out, "votes": vote_out, "vote_prior": round(prior, 4)}
    return out


def build(patch: str, pools: dict, sheets: dict[str, list[dict]], sheets_as_of: dict, ballots: list[dict]) -> dict:
    hash_to_name = {w["hash"]: norm(w["name"]) for w in pools["weapons"]}
    modes = {}
    for mode in ("pve", "pvp"):
        guns = join(pools, sheets.get(mode, []))
        rate(guns, mode)
        votes = learn_votes(ballots, guns, mode, hash_to_name)
        modes[mode] = (guns, votes)
    return freeze(patch, sheets_as_of, modes)
