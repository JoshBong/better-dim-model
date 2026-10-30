# DiS (Destiny Item Scorer) model

A gear-scoring model for Destiny 2 weapon rolls. It scores every roll 0 to 100 per mode (PvE, PvP) from the
community tier sheets and about 250k curator wishlist rolls, and is rebuilt for each game patch.

This repo is the model and the research behind it. Browse every scored weapon, and the math behind the score, in the [DiS vault](https://joshhuang.me/dis/). The browser extension that uses it (badges in
[DIM](https://app.destinyitemmanager.com), safe vault cleanup) is under construction.

## Results

AUC = the chance a roll curators endorse scores higher than one they don't, on the same gun. Parameters were
picked on Edge of Fate-era curator lists and tested on newer ones.

| | Model | Curators agreeing with each other |
|---|---|---|
| PvE | **0.82** | 0.68 |
| PvP | **0.89** | 0.79 |

A ridge-constrained logistic model was also tested; out of era it did no better than counting curator votes, so
it wasn't adopted. Every experiment, including the ones that didn't work, is written up in
[`research/README.md`](research/README.md).

## Layout

| Path | What |
|---|---|
| `better_dim/model.py` | per-patch model builder and freezer |
| `better_dim/curators.py` | curator ballots (mode and patch era) from the community wishlist collection |
| `models/dev-snapshot.json` | a frozen model: 1002 PvE and 1055 PvP guns |
| `research/` | every backtest and tuning script, with findings |
| `tests/` | model tests |

## Run

Python 3.11+, standard library only (tests need pytest).

```
python -m pytest tests
cd research && python parity.py      # PvE 0.814 / 0.817 with votes, PvP 0.864 / 0.890
python backtest.py                   # v2 vs binary and flat-floor baselines across curator eras
python ceiling.py                    # how well curators predict each other
```

## Data

All inputs needed to reproduce the results are in `research/data/`:
[dim-aegis-overlay](https://github.com/Maxeption/dim-aegis-overlay) (MIT) for the sheet mirror, perk pools and perk
names, and [dim-wish-list-sources](https://github.com/48klocs/dim-wish-list-sources) (MIT) for curator rolls. Two
sources used in the original research aren't redistributed here because they carry no license (the Just Another
Team wishlist, used only as an extra test set, and Clarity perk descriptions); the scripts run without them.

Unofficial fan project, not affiliated with Bungie.
