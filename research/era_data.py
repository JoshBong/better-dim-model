"""Which weapons existed in which era, for the historical (curators-only) models.

Bungie serves only the current manifest, so release dates come from DIM's d2-additional-info tables
(research/data/ext/d2ai: item hash -> season number, watermark -> season; MIT), taken per weapon NAME (the oldest
season among same-name hashes, so a reissue inherits the original's date), and from the curator lists themselves
(a name mentioned by a list of era k existed by era k). The table ends at season 28, so everything from
Edge of Fate on is dated to era 2 at the earliest; eras 0-2 cannot be told apart by season alone.

Era index follows better_dim.curators.ERAS (0 = newest). Season -> era thresholds: S1-15 Beyond Light & older,
S16-19 Witch Queen, S20-23 Lightfall, S24-26 Final Shape, S27-28 Edge of Fate / Ash & Iron, S29-30 Renegades,
S31+ Monument of Triumph.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("BD_DATA", os.path.join(HERE, "data"))
sys.path.insert(0, os.path.join(HERE, ".."))
from better_dim import curators, model  # noqa: E402

ERAS = [
    {"index": 0, "id": "monument-of-triumph", "label": "Monument of Triumph", "from": "2026-06", "to": None},
    {"index": 1, "id": "renegades", "label": "Renegades / Lawless", "from": "2025-12", "to": "2026-06"},
    {"index": 2, "id": "edge-of-fate", "label": "Edge of Fate / Ash & Iron", "from": "2025-07", "to": "2025-12"},
    {"index": 3, "id": "final-shape", "label": "The Final Shape episodes", "from": "2024-06", "to": "2025-07"},
    {"index": 4, "id": "lightfall", "label": "Lightfall", "from": "2023-02", "to": "2024-06"},
    {"index": 5, "id": "witch-queen", "label": "The Witch Queen", "from": "2022-02", "to": "2023-02"},
    {"index": 6, "id": "beyond-light", "label": "Beyond Light & older", "from": "2017-09", "to": "2022-02"},
]


def era_of_season(s: int) -> int:
    return 6 if s <= 15 else 5 if s <= 19 else 4 if s <= 23 else 3 if s <= 26 else 2 if s <= 28 else 1 if s <= 30 else 0


def load_tables():
    d = os.path.join(DATA, "ext", "d2ai")
    return (json.load(open(f"{d}/seasons.json")), json.load(open(f"{d}/seasons_backup.json")),
            json.load(open(f"{d}/watermark-to-season.json")))


def first_era(pools: dict, ballots: list[dict], manifest: list[dict] | None = None) -> dict[str, int]:
    """name -> oldest era index (largest number) in which the weapon existed."""
    seasons, backup, w2s = load_tables()
    wm = {w["hash"]: w.get("watermark", "") for w in (manifest or [])}

    def season_of(h: int):
        s = seasons.get(str(h)) or backup.get(str(h))
        if s:
            return int(s)
        for k, v in w2s.items():
            if k and k in wm.get(h, ""):
                return int(v)
        return None

    out: dict[str, int] = {}
    for w in pools["weapons"]:
        n = model.norm(w["name"])
        s = season_of(w["hash"])
        if s is not None:
            out[n] = max(out.get(n, -1), era_of_season(s))
    names = {w["hash"]: model.norm(w["name"]) for w in pools["weapons"]}
    for b in ballots:
        n = names.get(b["item"])
        if n:
            out[n] = max(out.get(n, -1), b["era"])
    return out


def available_in(era_index: int, first: dict[str, int]) -> set[str]:
    return {n for n, e in first.items() if e >= era_index}


def load_inputs():
    pools = json.load(open(f"{DATA}/ext/pools.json"))
    ballots = curators.parse(open(f"{DATA}/ext/wl/voltron.txt", errors="ignore").read())
    manifest = json.load(open(f"{DATA}/dim-aegis-overlay/data/manifest-weapons.json"))
    return pools, ballots, manifest


if __name__ == "__main__":
    pools, ballots, manifest = load_inputs()
    first = first_era(pools, ballots, manifest)
    print(f"{len(first)} of {len({model.norm(w['name']) for w in pools['weapons']})} pool names dated")
    for e in ERAS:
        print(f"era {e['index']} {e['label']:28s} weapons available: {len(available_in(e['index'], first))}")
