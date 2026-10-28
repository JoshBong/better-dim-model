import pytest

PERKS3 = {"outlaw": [101, 1101], "rapid hit": [102], "slideshot": [103], "zen moment": [104]}
PERKS4 = {"kill clip": [201, 1201], "rampage": [202], "frenzy": [203], "headstone": [204]}


def _entries(d):
    return [[h, n.title()] for n, hs in d.items() for h in hs]


def _gun(h, name):
    return {"hash": h, "name": name, "type": "Auto Rifle", "c3": _entries(PERKS3), "c4": _entries(PERKS4),
            "barrels": [[301, "Arrowhead Brake"], [302, "Smallbore"]], "mags": [[401, "Ricochet Rounds"], [402, "Flared Magwell"]]}


@pytest.fixture
def pools():
    # Echo is on no sheet; Alpha (Adept) is a variant with its own hash and no sheet row (the extension inherits Alpha's tier)
    return {"weapons": [_gun(1, "Alpha"), _gun(2, "Bravo"), _gun(3, "Charlie"), _gun(4, "Delta"), _gun(5, "Echo"), _gun(10, "Alpha (Adept)")]}


@pytest.fixture
def sheets():
    def row(name, p1, p2):
        return {"name": name, "tier": "A", "perk1": p1, "perk2": p2, "barrel": "Arrowhead Brake", "mag": "Ricochet Rounds"}
    rows = [row("Alpha", "Outlaw\nRapid Hit", "Kill Clip"), row("Bravo", "Outlaw", "Kill Clip\nRampage"),
            row("Charlie", "Rapid Hit", "Kill Clip"), row("Delta", "Outlaw", "Frenzy")]
    return {"pve": rows, "pvp": rows}


@pytest.fixture
def ballots():
    return [{"source": "x", "era": 0, "mode": "pve", "item": 1, "perks": [101, 201]},
            {"source": "y", "era": 0, "mode": "pve", "item": 2, "perks": [101, 202]}]
