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
    assert set(f["modes"]["pve"]["guns"]) == {"1", "2", "3", "4"}


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


def test_unknown_weapon_is_left_out(pools, sheets, ballots):
    sheets = {m: [r for r in rows if r["name"] != "Delta"] for m, rows in sheets.items()}
    f = model.build("v1", pools, sheets, {}, ballots)
    assert "4" not in f["modes"]["pve"]["guns"]
