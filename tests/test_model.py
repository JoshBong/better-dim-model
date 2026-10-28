from better_dim import model


def score(frozen, mode, gun, a, b):
    m = frozen["modes"][mode]
    g = m["guns"][str(gun)]
    prm = frozen["params"][mode]
    vp = frozen["vote_p"]
    raw = model.pmean(g["c3"][str(a)], g["c4"][str(b)], prm["p"]) + prm["mu"] * model.pmean(
        m["votes"].get(str(a), m["vote_prior"]), m["votes"].get(str(b), m["vote_prior"]), vp)
    return 100 * raw / g["best"]


def test_build_freezes_every_listed_gun(pools, sheets, ballots):
    f = model.build("v1", pools, sheets, {"pve": "t", "pvp": "t"}, ballots)
    assert f["patch"] == "v1"
    assert set(f["modes"]["pve"]["guns"]) == {"1", "2", "3", "4", "5"}  # 5 = Echo, estimated
    assert set(k for k, g in f["modes"]["pve"]["guns"].items() if g.get("est")) == {"5"}


def test_recommended_roll_beats_unlisted(pools, sheets, ballots):
    f = model.build("v1", pools, sheets, {}, ballots)
    good = score(f, "pve", 1, 101, 201)   # outlaw + kill clip, listed + endorsed
    bad = score(f, "pve", 1, 104, 204)    # zen moment + headstone, never picked
    assert good > bad
    assert 99 <= good < 100.01  # rounding; extension clamps to 100


def test_enhanced_hash_scores_same_as_base(pools, sheets, ballots):
    f = model.build("v1", pools, sheets, {}, ballots)
    g = f["modes"]["pve"]["guns"]["1"]
    assert g["c3"]["101"] == g["c3"]["1101"] and g["c4"]["201"] == g["c4"]["1201"]


def test_unknown_weapon_is_estimated_or_left_out(pools, sheets, ballots):
    sheets = {m: [r for r in rows if r["name"] != "Delta"] for m, rows in sheets.items()}
    f = model.build("v1", pools, sheets, {}, ballots)
    assert f["modes"]["pve"]["guns"]["4"]["est"] is True          # off the sheet: estimated, flagged
    f = model.build("v1", pools, sheets, {}, ballots, estimates=False)
    assert "4" not in f["modes"]["pve"]["guns"]                    # without estimates: left out as before


def test_off_sheet_gun_gets_an_estimate(pools, sheets, ballots):
    # Echo is on no sheet: every perk gets the unlisted formula with strength from the rated Auto Rifles.
    f = model.build("v1", pools, sheets, {}, ballots)
    g = f["modes"]["pve"]["guns"]["5"]
    assert g["est"] is True and g["tier"] == ""
    assert "est" not in f["modes"]["pve"]["guns"]["1"]
    # Outlaw / Kill Clip are what the sheets pick on the other Auto Rifles, so they estimate highest
    assert g["c3"]["101"] == max(g["c3"].values()) and g["c4"]["201"] == max(g["c4"].values())
    assert score(f, "pve", 5, 101, 201) > score(f, "pve", 5, 104, 204)
    assert model.build("v1", pools, sheets, {}, ballots, estimates=False)["modes"]["pve"]["guns"].get("5") is None


def test_era_model_is_curators_only(pools, sheets, ballots):
    old = ballots + [{"source": "z", "era": 2, "mode": "pve", "item": 3, "perks": [103, 203]}]
    era = {"id": "era-2", "index": 2, "label": "Edge of Fate"}
    f = model.build_era(era, pools, old, available={"alpha", "charlie"})
    assert f["kind"] == "curators" and f["era"]["index"] == 2 and f["patch"] == "era-2"
    guns = f["modes"]["pve"]["guns"]
    assert set(guns) == {"1", "3"}                      # Bravo, Delta and Echo did not exist in that era
    assert all(g["est"] for g in guns.values())
    # only era-2-or-older ballots count: the era-0 ballots for Alpha/Bravo are ignored, Charlie's Slideshot/Frenzy wins
    assert score(f, "pve", 3, 103, 203) > score(f, "pve", 3, 101, 201)
    assert score(f, "pve", 1, 101, 201) == score(f, "pve", 1, 104, 204)  # no signal for Alpha in that era: flat
