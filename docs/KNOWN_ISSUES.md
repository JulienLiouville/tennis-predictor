Known Issues
Critical
Surface Unknown Problem

Impact:

training dataset becomes empty.

Cause:

surfaces imported as "Unknown".

Fix:

run fix_surfaces.py before setup.

Status:

partially fixed.
Recent Matches Features Missing

Impact:

recent ATP/WTA matches use default fake features.

Fix:

extend precompute_features.py to matches_2026.

Status:

not implemented.
Potential Temporal Leakage

Impact:

unrealistic backtests.

Fix:

enforce temporal splits.

Status:

partially fixed.
Important
ATP/WTA Combined Model

Potential issue:

different statistical behaviors.

Status:

not benchmarked.
No Probability Calibration

Impact:

80% confidence may not mean real 80%.

Fix:

add CalibratedClassifierCV.

Status:

pending.