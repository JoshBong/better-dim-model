"""Mock gear-score evaluation against Aegis (PvE) and Finnald (PvP) sheet data.

Usage: python3 -I gearscore.py <data_dir>
"""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("BD_DATA", os.path.join(HERE, "data"))
import json
import random
import re
import sys
from collections import Counter
from itertools import product

DATA = sys.argv[1]
random.seed(7)

pve = json.load(open(f"{DATA}/pve-database.json"))["weapons"]
pvp = json.load(open(f"{DATA}/pvp-database.json"))["weapons"]
manifest = json.load(open(f"{DATA}/manifest-weapons.json"))


def norm(s: str) -> str:
    s = s.lower().replace("enhanced", "").replace("’", "'")
    return re.sub(r"[^a-z0-9']+", " ", s).strip()


def split_list(s: str) -> list[str]:
    return [norm(x) for x in re.split(r"[\n/,]+", s or "") if x.strip()]


# Manifest: keep entries with two trait columns; key by normalized name.
by_name: dict[str, list] = {}
for m in manifest:
    cols = m.get("perkColumns") or []
    if len(cols) >= 2 and m.get("tierName") == "Legendary":
        by_name.setdefault(norm(m["name"]), []).append(m)


def base_name(name: str) -> str:
    return norm(re.sub(r"\(.*?\)", "", name))


def pick_variant(w):
    """Reissues share names; pick the manifest variant whose pool covers the most recs."""
    cands = by_name.get(norm(w["name"])) or by_name.get(base_name(w["name"])) or []
    recs = split_list(w.get("perk1", "")) + split_list(w.get("perk2", ""))
    def cover(m):
        pool = {norm(x) for c in m["perkColumns"] for x in c}
        return sum(r in pool for r in recs)
    return max(cands, key=cover) if cands else None


def build(sheet: dict) -> dict:
    """Join sheet entries to manifest columns; report name-match quality."""
    out, stats = {}, Counter()
    for key, w in sheet.items():
        p1, p2 = split_list(w.get("perk1", "")), split_list(w.get("perk2", ""))
        if not p1 or not p2:
            stats["no_recs"] += 1
            continue
        m = pick_variant(w)
        if not m:
            stats["no_manifest"] += 1
            continue
        c3 = [norm(x) for x in m["perkColumns"][0]]
        c4 = [norm(x) for x in m["perkColumns"][1]]
        barrels = [norm(x) for x in m.get("barrels") or []]
        mags = [norm(x) for x in m.get("magazines") or m.get("mags") or []]
        # Sheet perks may belong to either column; place each by membership.
        r3 = [p for p in p1 if p in c3] + [p for p in p2 if p in c3 and p not in p1]
        r4 = [p for p in p2 if p in c4] + [p for p in p1 if p in c4 and p not in p2]
        stats["recs_total"] += len(p1) + len(p2)
        stats["recs_matched"] += len(set(r3)) + len(set(r4))
        if not r3 or not r4:
            stats["unmatched_after_join"] += 1
            continue
        stats["usable"] += 1
        out[key] = dict(
            name=w["name"], tier=w.get("tier", ""),
            c3=c3, c4=c4, barrels=barrels, mags=mags,
            r3=r3, r4=r4,
            rb=split_list(w.get("barrel", "")), rm=split_list(w.get("mag", "")),
        )
    return out, stats


RANK_VALUES = [1.0, 0.9, 0.8, 0.75, 0.7]


def trait_value(perk: str, recs: list[str], floor: float) -> float:
    if perk in recs:
        i = recs.index(perk)
        return RANK_VALUES[min(i, len(RANK_VALUES) - 1)]
    return floor


def score(w, opts3, opts4, barrel, mag, floor=0.15, combine="geo") -> float:
    t3 = max(trait_value(p, w["r3"], floor) for p in opts3)
    t4 = max(trait_value(p, w["r4"], floor) for p in opts4)
    roll = (t3 * t4) ** 0.5 if combine == "geo" else (t3 + t4) / 2
    extras = 0.9 + 0.05 * (barrel in w["rb"]) + 0.05 * (mag in w["rm"])
    return 100 * roll * extras


def maxeption_grade(w, opts3, opts4, barrel, mag) -> str:
    """Their default computeGrade with selectable-as-active, origin assumed present."""
    p1 = any(p in w["r3"] for p in opts3)
    p2 = any(p in w["r4"] for p in opts4)
    m, b = mag in w["rm"], barrel in w["rb"]
    if p1 and p2 and m and b:
        return "S+"
    if p1 and p2 and m:
        return "S"
    if p1 and p2 and b:
        return "A+"
    if p1 and p2:
        return "A"
    if (p1 or p2) and (m or b):
        return "C"
    if p1 or p2:
        return "D"
    return "F"


GRADE_ORDER = {"S+": 6, "S": 5, "A+": 4, "A": 3, "C": 2, "D": 1, "F": 0}


def sample_roll(w, per_col=1):
    o3 = random.sample(w["c3"], min(per_col, len(w["c3"])))
    o4 = random.sample(w["c4"], min(per_col, len(w["c4"])))
    b = random.choice(w["barrels"]) if w["barrels"] else ""
    m = random.choice(w["mags"]) if w["mags"] else ""
    return o3, o4, b, m


def spearman(xs, ys) -> float:
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2
            i = j + 1
        return r
    rx, ry = ranks(xs), ranks(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = sum((a - mx) ** 2 for a in rx) ** 0.5
    vy = sum((b - my) ** 2 for b in ry) ** 0.5
    return cov / (vx * vy)


def band(s, keep=80, floor=50):
    return "keep" if s >= keep else ("maybe" if s >= floor else "trash")


def run_mode(label, db, n=400):
    print(f"\n=== {label}: {len(db)} usable weapons ===")
    geo, summ, grades, bands = [], [], [], Counter()
    misled = 0
    per_weapon_keep = []
    for w in db.values():
        keeps = 0
        for _ in range(n):
            o3, o4, b, m = sample_roll(w)
            g = score(w, o3, o4, b, m)
            s = score(w, o3, o4, b, m, combine="sum")
            geo.append(g)
            summ.append(s)
            grades.append(GRADE_ORDER[maxeption_grade(w, o3, o4, b, m)])
            bands[band(g)] += 1
            keeps += g >= 80
            if s >= 50 and g < 40:
                misled += 1
        per_weapon_keep.append(keeps / n)
    total = len(geo)
    print("score bands (1 perk/col drops):", {k: f"{v / total:.1%}" for k, v in bands.items()})
    pk = sorted(per_weapon_keep)
    print(f"per-weapon keep rate: median {pk[len(pk) // 2]:.1%}, p10 {pk[len(pk) // 10]:.1%}, p90 {pk[9 * len(pk) // 10]:.1%}")
    print(f"sum-formula would call >=50 but geo <40 (one good + one junk trait): {misled / total:.1%} of drops")
    print(f"Spearman(geo score, Maxeption grade): {spearman(geo, grades):.3f}")
    # 2 perks per column (raid/higher-tier drops)
    b2 = Counter()
    for w in db.values():
        for _ in range(n // 4):
            o3, o4, b, m = sample_roll(w, per_col=2)
            b2[band(score(w, o3, o4, b, m))] += 1
    t2 = sum(b2.values())
    print("score bands (2 perks/col drops):", {k: f"{v / t2:.1%}" for k, v in b2.items()})
    # floor sensitivity
    for fl in (0.0, 0.3):
        c = Counter()
        for w in db.values():
            for _ in range(n // 4):
                o3, o4, b, m = sample_roll(w)
                c[band(score(w, o3, o4, b, m, floor=fl))] += 1
        t = sum(c.values())
        print(f"  floor={fl}: ", {k: f"{v / t:.1%}" for k, v in c.items()})


def resolution_check(label, db):
    """Within Maxeption's top grade, how much does rank-aware scoring separate rolls?"""
    spread = []
    for w in db.values():
        vals = set()
        for p3, p4 in product(w["r3"], w["r4"]):
            vals.add(round(score(w, [p3], [p4], w["rb"][0] if w["rb"] else "", w["rm"][0] if w["rm"] else "")))
        spread.append(len(vals))
    c = Counter(min(x, 6) for x in spread)
    print(f"{label}: distinct scores among rolls Maxeption grades identically (both traits recommended): {dict(sorted(c.items()))}")


def show_examples(db_e, db_p, names):
    for nm in names:
        k = norm(nm)
        we, wp = db_e.get(k), db_p.get(k)
        if not we:
            continue
        print(f"\n--- {we['name']} (PvE tier {we['tier']}{', PvP tier ' + wp['tier'] if wp else ''})")
        print("  PvE recs col3:", we["r3"], "| col4:", we["r4"])
        if wp:
            print("  PvP recs col3:", wp["r3"], "| col4:", wp["r4"])
        cands = [
            (we["r3"][0], we["r4"][0], "PvE #1/#1"),
            (we["r3"][-1], we["r4"][-1], "PvE last-listed/last-listed"),
            (we["r3"][0], next((p for p in we["c4"] if p not in we["r4"]), we["c4"][0]), "PvE #1 + unlisted"),
        ]
        if wp:
            cands.append((wp["r3"][0], wp["r4"][0], "PvP #1/#1"))
        for p3, p4, tag in cands:
            b = we["rb"][0] if we["rb"] else ""
            m = we["rm"][0] if we["rm"] else ""
            se = score(we, [p3], [p4], b, m)
            sp = score(wp, [p3], [p4], wp["rb"][0] if wp and wp["rb"] else "", wp["rm"][0] if wp and wp["rm"] else "") if wp else None
            mg = maxeption_grade(we, [p3], [p4], b, m)
            print(f"  {tag:30s} {p3} + {p4}: PvE {se:5.1f} ({band(se)}, Maxeption {mg})"
                  + (f" | PvP {sp:5.1f} ({band(sp)})" if sp is not None else ""))


db_e, st_e = build(pve)
db_p, st_p = build(pvp)
print("PvE join:", dict(st_e), f"perk-name match {st_e['recs_matched'] / st_e['recs_total']:.1%}")
print("PvP join:", dict(st_p), f"perk-name match {st_p['recs_matched'] / st_p['recs_total']:.1%}")

run_mode("PvE (Aegis)", db_e)
run_mode("PvP (Finnald)", db_p)
resolution_check("PvE", db_e)
resolution_check("PvP", db_p)

# Cross-mode disagreement on identical rolls
both = set(db_e) & set(db_p)
dis, tot, ge, gp = Counter(), 0, [], []
for k in both:
    we, wp = db_e[k], db_p[k]
    if we["c3"] != wp["c3"]:
        continue
    for _ in range(200):
        o3, o4, b, m = sample_roll(we)
        a, c = score(we, o3, o4, b, m), score(wp, o3, o4, b, m)
        ge.append(a)
        gp.append(c)
        dis[(band(a), band(c))] += 1
        tot += 1
print(f"\nCross-mode on {len(both)} shared weapons, Spearman(PvE, PvP) = {spearman(ge, gp):.3f}")
print("  keep in one mode, trash in other:", f"{(dis[('keep','trash')] + dis[('trash','keep')]) / tot:.1%}",
      "| keep in both:", f"{dis[('keep','keep')] / tot:.1%}")

show_examples(db_e, db_p, ["Cusp Sempiternal", "Abyss Defiant", "Fatebringer", "Igneous Hammer", "Gjallarhorn", "Unworthy", "Rose", "Mountaintop", "Austringer", "Fixed Odds"])
