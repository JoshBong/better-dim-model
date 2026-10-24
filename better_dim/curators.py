"""Curator ballots from the community DIM wishlist collection (48klocs/dim-wish-list-sources, MIT).

Each wishlist line becomes a ballot tagged with mode (PvE/PvP) and patch era (0 = current patch family).
Era comes from the source list's title, since lists are named after the season/episode they cover.
"""
import re
import urllib.request

VOLTRON = "https://raw.githubusercontent.com/48klocs/dim-wish-list-sources/master/voltron.txt"

# Newest first; index = era (0 newest). First pattern that matches the list title wins.
ERAS = [
    r"pve podcast 1(6[5-9]|7\d)|machine guns|guardian games 2026|iron banner 2026|ab rolls 4\d",   # Monument of Triumph
    r"renegades|lawless|equilibrium|pve podcast 16[0-4]|arms week 2026|dawning 2025",            # Renegades / Lawless
    r"edge of fate|kepler|ash (and|&) iron|pve podcast 15\d",                                     # Edge of Fate / Ash & Iron
    r"final shape|revenant|heresy|echoes|rite of the nine|ep13\d|pve podcast 1[34]\d|vault of glass weapon refresh",
    r"season 2[0-3]|s2[0-3]\b|defiance|deep|into the light|witch\b|wish|lightfall|guardian games \(2024\)|season 22",
    r"\bwq\b|witch queen|s1[6-9]\b|season 1[6-9]|risen|haunted|plunder|seraph|30th|kings fall|vow",
    r"s1[0-5]\b|season 1[0-5]|chosen|season of the lost|sharditkeepit|podcast 2\d\d|splicer|hunt\b",
]

LINE = re.compile(r"^dimwishlist:item=(-?\d+)(?:&perks=)?([\d,]*)(?:#notes:)?(.*)$")


def era_of(title: str) -> int | None:
    t = title.lower()
    for i, pat in enumerate(ERAS):
        if re.search(pat, t):
            return i
    return None


def mode_of(text: str) -> str | None:
    t = text.lower()
    pve = bool(re.search(r"\bpve\b|pve[-/]|\(pve|red bar|dps|add clear", t))
    pvp = bool(re.search(r"\bpvp\b|pvp[-/]|\(pvp|crucible|trials|gambit", t))
    if pve != pvp:
        return "pve" if pve else "pvp"
    return None


def parse(text: str) -> list[dict]:
    title = header = block_notes = ""
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("title:"):
            title = line[6:]
        elif line.startswith("//notes:"):
            block_notes = line[8:]
        elif line.startswith("//"):
            if not line.startswith("// ("):
                header = line[2:].strip()
        elif not line:
            block_notes = ""
        else:
            m = LINE.match(line)
            if not m or int(m.group(1)) < 0:
                continue
            era = era_of(title)
            mode = mode_of(m.group(3)) or mode_of(block_notes) or mode_of(header) or mode_of(title)
            if era is None or mode is None:
                continue
            out.append({"source": title, "era": era, "mode": mode, "item": int(m.group(1)),
                        "perks": [int(x) for x in m.group(2).split(",") if x]})
    return out


def fetch() -> list[dict]:
    req = urllib.request.Request(VOLTRON, headers={"User-Agent": "better-dim"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return parse(r.read().decode("utf-8", errors="ignore"))
