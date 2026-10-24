"""Shared loading/joining for gear-score experiments."""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("BD_DATA", os.path.join(HERE, "data"))
import json
import re
from collections import Counter

OVERLAY_DATA = DATA + "/dim-aegis-overlay/data"
CLARITY = DATA + "/ext/clarity/descriptions/braytech.json"


def norm(s: str) -> str:
    s = s.lower().replace("enhanced", "").replace("’", "'")
    return re.sub(r"[^a-z0-9']+", " ", s).strip()


def split_list(s: str) -> list[str]:
    return [norm(x) for x in re.split(r"[\n/,]+", s or "") if x.strip()]


def load():
    pve = json.load(open(f"{OVERLAY_DATA}/pve-database.json"))["weapons"]
    pvp = json.load(open(f"{OVERLAY_DATA}/pvp-database.json"))["weapons"]
    manifest = json.load(open(f"{OVERLAY_DATA}/manifest-weapons.json"))
    by_name: dict[str, list] = {}
    for m in manifest:
        if len(m.get("perkColumns") or []) >= 2 and m.get("tierName") == "Legendary":
            by_name.setdefault(norm(m["name"]), []).append(m)
    return pve, pvp, by_name


def pick_variant(w, by_name):
    """Reissues share names; pick the manifest variant whose pool covers the most recs."""
    base = norm(re.sub(r"\(.*?\)", "", w["name"]))
    cands = by_name.get(norm(w["name"])) or by_name.get(base) or []
    recs = split_list(w.get("perk1", "")) + split_list(w.get("perk2", ""))

    def cover(m):
        pool = {norm(x) for c in m["perkColumns"] for x in c}
        return sum(r in pool for r in recs)

    return max(cands, key=cover) if cands else None


def build(sheet, by_name):
    out = {}
    for key, w in sheet.items():
        p1, p2 = split_list(w.get("perk1", "")), split_list(w.get("perk2", ""))
        if not p1 or not p2:
            continue
        m = pick_variant(w, by_name)
        if not m:
            continue
        c3 = list(dict.fromkeys(norm(x) for x in m["perkColumns"][0]))
        c4 = list(dict.fromkeys(norm(x) for x in m["perkColumns"][1]))
        r3 = [p for p in p1 if p in c3] + [p for p in p2 if p in c3 and p not in p1]
        r4 = [p for p in p2 if p in c4] + [p for p in p1 if p in c4 and p not in p2]
        if not r3 or not r4:
            continue
        out[key] = dict(
            name=w["name"], tier=w.get("tier", ""), wtype=m["typeName"], hash=m["hash"],
            c3=c3, c4=c4,
            barrels=[norm(x) for x in m.get("barrels") or []],
            mags=[norm(x) for x in m.get("magazines") or []],
            r3=list(dict.fromkeys(r3)), r4=list(dict.fromkeys(r4)),
            rb=split_list(w.get("barrel", "")), rm=split_list(w.get("mag", "")),
            notes=w.get("notes", ""),
        )
    return out


def descriptions():
    if not os.path.exists(CLARITY):   # Clarity data isn't redistributed; see README
        return {}
    d = json.load(open(CLARITY))
    out = {}
    for v in d.values():
        if v.get("type") in ("Weapon Trait", "Weapon Trait Enhanced", "Weapon Perk"):
            out.setdefault(norm(v["name"]), v["descriptions"].get("en", ""))
    return out
