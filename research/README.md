# Gear-score research

These are the experiments behind `server/better_dim/model.py`. All of them are offline backtests: rolls are
scored and then compared against which rolls curators actually endorsed.

**Metric: AUC.** On each gun, it's the chance that a trait pair curators endorse scores higher than one they
don't. It's averaged over guns. Curators agree with each other at about 0.68–0.79 (`ceiling.py`), so that's
roughly the ceiling.

## Data (in `research/data/`)

All inputs are committed, so every script runs straight from the repo. Set `$BD_DATA` to point somewhere
else.

| Path | What | Source |
|---|---|---|
| `dim-aegis-overlay/data/{pve,pvp}-database.json` | Aegis PvE and Finnald PvP sheet mirror, as of 2026-10-22 | Maxeption/dim-aegis-overlay (MIT) |
| `dim-aegis-overlay/data/manifest-weapons.json`, `src/canonical-hashes.ts` | weapon perk pools and perk hashes | same |
| `ext/wl/voltron.txt` | about 250k curator rolls, as of 2026-09-17 | 48klocs/dim-wish-list-sources (MIT) |
| `ext/jat/bundles/DIM/just-another-team-mnk.txt` | Just Another Team wishlist, used only as an extra test set | **not included** (no license); scripts skip it when absent |
| `ext/clarity/descriptions/` | perk descriptions, read when checking perks by hand | **not included** (no license); perk names fall back to `dim-aegis-overlay/src/canonical-hashes.ts` with identical backtest results |
| `ext/pools.json` | pools in the extension's upload format (`server/tests/make_fixture_pools.py`) | derived |

## Findings, in order

| Step | Script | Result |
|---|---|---|
| v1: binary "listed or not" score, like Maxeption's | `gearscore.py`, `diag.py`, `hist.py` | Too harsh, and every unlisted perk was treated the same |
| v2: rank decay for listed perks, a strength model for unlisted ones, power mean across columns | `gearscore_v2.py`, `validate_v2.py`, `cases.py`, `robust_v2.py` | Hand-checked against what the perks actually do; robust to parameter wiggle |
| Backtest against Reddit, site and curator rolls | `backtest.py`, `siterolls.py`, `wishlists.py` | v2 beats the binary grade. AUC is about 0.79 PvE and 0.80 PvP on post-Edge-of-Fate sources |
| Inter-curator ceiling | `ceiling.py` | Curators agree at 0.68–0.79, so v2 is at the ceiling |
| Can a perk be worth less than nothing? | `tune.py`, `calib.py` | Negative values change nothing |
| Patch-era effects | `era_backtest.py`, `calib_era.py` | PvE accuracy decays as sources get older (meta drift); PvP is stable. Herd behaviour doesn't explain the agreement |
| Pair synergy (does a specific perk *pair* matter beyond its two perks?) | `synergy.py`, `explain_votes.py` | No gain; it only learns noise. Curator votes per perk do help, and became `mu * vote` |
| Ridge-constrained logistic: a per-perk ball tP plus a per-perk-per-type ball tT, fit by projected gradient descent | `ridge.py`, `ridge_grid.py`, `ridge_diag.py`, `ridge_grid.json` | U-shaped curve in t. On an honest split (choose t on Edge of Fate, test later) it's no better than counting votes, so it wasn't adopted |
| Separate parameters for PvE and PvP | `tune_mode.py`, `tune_mode_wide.py` | Adopted (table below) |
| Production builder matches research | `parity.py` | PvE 0.814, or 0.817 with votes (n=108); PvP 0.864, or 0.890 with votes (n=20) |
| Scoring guns that aren't on the sheet | `offsheet.py` | Holds up; see below |

### Adopted parameters (`model.PARAMS`)

| | rank decay | unlisted cap | gamma | column power mean p | vote weight mu | vote recency per era |
|---|---|---|---|---|---|---|
| PvE | 0.20 | 0.7 | 1.0 | 0 (geometric) | 1.0 | 1.0 |
| PvP | 0.15 | 0.7 | 0.8 | 0.5 | 1.0 | 0.6 |

The parameters were chosen on Edge of Fate-era curator lists (136 lists, validation AUC 0.828 against 0.800
for one shared setting). They were then tested on newer sources:

| Test set | Shared params | Per-mode params |
|---|---|---|
| PvE, post-EoF curators | 0.805 | 0.816 |
| PvP, post-EoF curators (n=21) | 0.865 | 0.894 |
| PvP, JAT Dec 2025 (n=427) | 0.781 | 0.851 |

### Guns not on the sheet (`offsheet.py`)

Sheet guns were scored with their sheet entry hidden (leave-one-out strength only). Separately, pool guns that
are really missing from the sheet were scored with strength taken from every sheet gun.

| | Full model | Sheet hidden | Really off-sheet |
|---|---|---|---|
| PvE | 0.818 | 0.799 | 0.762 (n=10) |
| PvP | 0.886 | 0.877 | 0.799 (n=3) |

Hiding the sheet entry costs about 0.01–0.02. There are too few real off-sheet samples to rely on yet. This
isn't in `model.py` yet.

## Frozen model

`models/dev-snapshot.json` is the current model, frozen from the inputs above: 1002 PvE and 1055 PvP guns,
about 1.5 MB, or 230 KB gzipped. Pools come from a manifest snapshot, not a live DIM manifest, so its
`patch` is `dev-snapshot`. Production models are built by the server for each real patch.
