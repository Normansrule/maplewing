# Real thrust curves (2026-11-03)

Source: ThrustCurve.org API v1 (search.json, download.json), within its robots.txt and llms.txt terms (rate limited, cited by simfile page). Details per motor in `motors.json`.

| Motor | Curve file | Source type | Curve impulse (N·s) | Old assumed (N·s) |
|---|---|---|---|---|
| Estes A8-3 | [simfile](https://www.thrustcurve.org/simfiles/5f4294d20002e900000004e3/) | NAR certification data | 2.32 | 2.5 |
| Estes B6-4 | [simfile](https://www.thrustcurve.org/simfiles/5f4294d20002e90000000414/) | NAR certification data | 4.33 | 5.0 |
| Estes C6-5 | [simfile](https://www.thrustcurve.org/simfiles/69eb2379c7d63000021d8c29/) | NAR certification data | 8.82 | 10.0 |
| Estes D12-5 | [simfile](https://www.thrustcurve.org/simfiles/5f4294d20002e900000004ea/) | user upload, made from NAR data | 16.84 | 20.0 |
| AeroTech H128W | [simfile](https://www.thrustcurve.org/simfiles/5f4294d20002e9000000000d/) | Tripoli (TRA) test stand 1997 | 177.8 | 175 |
| AeroTech J350W | [simfile](https://www.thrustcurve.org/simfiles/5f4294d20002e900000002a9/) | user upload, no source note | 669 | 700 |

Masses come from the ThrustCurve motor record (certification data). The J350W curve is the only file on the site and integrates to about 4% below the 700 N·s record; replace it if a certified file appears. A delay number does not change the curve.

## Apogee shift (1,300 m site, same airframes and drag)

| Design | Old | New | Change | RocketPy (6-DOF) |
|---|---|---|---|---|
| Seedling model, 3 fins (C6-5) | 377 m | 317 m | −16.0% | 317 m |
| Seedling model, ring tail (C6-5) | 312 m | 263 m | −15.9% | 263 m |
| Sapling L1, 3 fins (H128W) | 513 m | 542 m | +5.8% | 543 m |
| Sapling L1, ring tail (H128W) | 430 m | 455 m | +5.8% | 456 m |
| Sapling L2, ring tail (J350W) | 806 m | 763 m | −5.4% | 764 m |
| Taproot, A8-3 | 87 m | 76 m | −12.9% | 76 m |
| Taproot, B6-4 | 205 m | 172 m | −16.1% | 172 m |
| Taproot, C6-5 | 376 m | 346 m | −7.9% | 346 m |

Python/browser agreement test: pass (worst apogee difference 0.00%, margin 0.000 cal).

## Taproot drag recalibration (2026-11-04)
Taproot's drag coefficient (Cd) was calibrated to Estes' published 351 m using the old 10 N·s C6. With the real curve, Cd 0.643 reproduces 351 m at sea level, so Taproot now uses 0.643 (sim and configurator).

| Taproot motor | 1,300 m site, Cd 0.75 | 1,300 m site, Cd 0.643 |
|---|---|---|
| A8-3 | 76 m | 78 m |
| B6-4 | 172 m | 183 m |
| C6-5 | 346 m | 376 m |

The ring-tail and Sapling Cd values are still assumptions, not calibrations; drone drops, swing tests and first flights replace them.

## Motor ladder additions (2026-11-04)
Added Estes E16 ([simfile](https://www.thrustcurve.org/simfiles/5f4294d20002e900000007e6/), matches NAR cert averages), Estes F26 ([simfile](https://www.thrustcurve.org/simfiles/5fc5ac0c995c080004e6edc8/), AeroTech pre-cert data) and AeroTech G40W ([simfile](https://www.thrustcurve.org/simfiles/5f4294d20002e90000000463/), AeroTech-supplied) for `motor_ladder.py`. Estes E12 is listed out of production. Python/browser agreement test still passes.
