"""Parse DIM wishlist files into (source, curator_title, mode, item_hash, trait perk names)."""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("BD_DATA", os.path.join(HERE, "data"))
import glob
import json
import re

from common import norm

HASH_NAME = {}
for f in glob.glob(DATA + "/ext/clarity/descriptions/*.json"):
    for k, v in json.load(open(f)).items():
        if "Weapon" in (v.get("type") or "") and v.get("name"):
            HASH_NAME.setdefault(int(k), norm(v["name"]))
if not HASH_NAME:   # Clarity isn't redistributed; fall back to the MIT perk table from dim-aegis-overlay
    ts = open(DATA + "/dim-aegis-overlay/src/canonical-hashes.ts").read()
    table = json.loads(re.search(r"HASH_TO_ENGLISH_PERK[^=]*=\s*(\{.*?\})\s*;", ts, re.S).group(1))
    HASH_NAME = {int(k): norm(v) for k, v in table.items()}

ITEM_NAME = {m["hash"]: m["name"] for m in json.load(open(DATA + "/dim-aegis-overlay/data/manifest-weapons.json"))}

LINE = re.compile(r"^dimwishlist:item=(-?\d+)(?:&perks=)?([\d,]*)(?:#notes:)?(.*)$")


def mode_of(text: str):
    t = text.lower()
    pve = bool(re.search(r"\bpve\b|pve[-/]|\(pve|red bar|dps|add clear", t))
    pvp = bool(re.search(r"\bpvp\b|pvp[-/]|\(pvp|crucible|trials|gambit", t))
    if pve and not pvp:
        return "pve"
    if pvp and not pve:
        return "pvp"
    return None


def parse(path, source):
    title, header, block_notes = "", "", ""
    out = []
    for raw in open(path, encoding="utf-8", errors="ignore"):
        line = raw.strip()
        if line.startswith("title:"):
            title = line[6:]
            continue
        if line.startswith("//notes:"):
            block_notes = line[8:]
            continue
        if line.startswith("//"):
            if not line.startswith("// ("):
                header = line[2:].strip()
            continue
        if not line:
            block_notes = ""
            continue
        m = LINE.match(line)
        if not m:
            continue
        item = int(m.group(1))
        if item < 0 or item not in ITEM_NAME:
            continue
        perks = [HASH_NAME.get(int(x)) for x in m.group(2).split(",") if x]
        perks = [p for p in perks if p]
        mode = mode_of(m.group(3)) or mode_of(block_notes) or mode_of(header) or mode_of(title)
        out.append(dict(source=source, title=title, header=header, mode=mode,
                        weapon=ITEM_NAME[item], perks=perks, notes=(m.group(3) or block_notes)))
    return out
