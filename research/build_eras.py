"""Freeze the historical era models + models/index.json (and refresh models/dev-snapshot.json with estimates).

Usage: python build_eras.py
Writes models/eras/<id>.json for every era from Final Shape backwards (eras 0-2 are covered by the latest model:
too few lists to stand alone, and the sheet is current there), and models/index.json listing them.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
from better_dim import model as M  # noqa: E402
import era_data  # noqa: E402

OUT = os.path.join(HERE, "..", "models")
pools, ballots, manifest = era_data.load_inputs()
first = era_data.first_era(pools, ballots, manifest)
sheets = {m: list(json.load(open(f"{era_data.DATA}/dim-aegis-overlay/data/{m}-database.json"))["weapons"].values()) for m in ("pve", "pvp")}

latest = M.build("dev-snapshot", pools, sheets,
                 {"pve": "2026-10-22 (Aegis via dim-aegis-overlay data mirror)", "pvp": "2026-10-22 (Finnald via dim-aegis-overlay data mirror)"},
                 ballots)
latest["note"] = ("Dev build from offline inputs; perk pools rebuilt from the dim-aegis-overlay manifest snapshot, not a live DIM "
                  "manifest. Curator ballots: dim-wish-list-sources voltron @ 0d0f687 (2026-09-17). Off-sheet guns are estimates (est).")
json.dump(latest, open(f"{OUT}/dev-snapshot.json", "w"), separators=(",", ":"))

os.makedirs(f"{OUT}/eras", exist_ok=True)
index = {"latest": {"id": "latest", "label": "Latest (sheet + curators)", "file": "dev-snapshot.json", "kind": "sheet+curators"}, "eras": []}
for era in era_data.ERAS:
    if era["index"] < 3:
        continue
    f = M.build_era(era, pools, ballots, available=era_data.available_in(era["index"], first))
    path = f"eras/{era['id']}.json"
    json.dump(f, open(f"{OUT}/{path}", "w"), separators=(",", ":"))
    n = {m: len(f["modes"][m]["guns"]) for m in ("pve", "pvp")}
    index["eras"].append({**era, "file": path, "kind": "curators", "guns": n})
    print(f"{path}: {n} bytes={os.path.getsize(f'{OUT}/{path}')}")
json.dump(index, open(f"{OUT}/index.json", "w"), indent=2)
print(f"dev-snapshot.json bytes={os.path.getsize(f'{OUT}/dev-snapshot.json')} guns pve={len(latest['modes']['pve']['guns'])} "
      f"(est {sum(1 for g in latest['modes']['pve']['guns'].values() if g.get('est'))}) pvp={len(latest['modes']['pvp']['guns'])}")
