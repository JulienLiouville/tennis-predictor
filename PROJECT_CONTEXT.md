🎾 Tennis Predictor — Updated Project Status (May 2026)
Current Global State

The project has moved from:

"broken prototype pipeline"

to:

"statistical validation and ML reliability phase"

The architecture is now considered:

modular,
scalable,
maintainable,
suitable for future MLOps evolution.
✅ Major Fixes Successfully Completed
1. Surface Normalization Fixed

Previous state:

444k+ matches had NULL/Unknown surfaces.

Current state:

surfaces correctly normalized,
realistic distribution:
Clay,
Hard,
Grass.

Impact:

recent dataset is now usable,
surface feature becomes statistically meaningful.
2. Duplicate Matches Fixed

Previous state:

massive duplicate corruption in matches_2026.

Current state:

duplicate validation passes successfully.

Impact:

cleaner training dataset,
reduced statistical pollution,
more trustworthy backtesting.
3. Feature Generation Fixed

Current state:

match_features now contains 380k+ rows.

Observed feature quality:

Feature	Status
momentum_l5	healthy variance
momentum_l10	healthy variance
fatigue_7d	realistic distribution
H2H ratio	sparse / fallback-heavy

Impact:

project now uses real engineered features instead of fallback defaults.
4. Validation Infrastructure Added

A complete validation script now exists:

quick.py

Purpose:

healthcheck system,
database integrity validation,
feature sanity checks,
leakage detection,
pipeline verification.

This script is now considered a core project component.

⚠️ Current Known Weaknesses
1. Winner / Target Integrity Investigation

Current critical issue:

ValueError: y contains 1 class

Possible causes:

corrupted winner column,
player1 always stored as winner,
invalid target generation.

This is currently the highest-priority validation task.

Required SQL validation:

SELECT
    COUNT(*) as total,
    SUM(CASE WHEN player1 = winner THEN 1 ELSE 0 END) as p1_wins,
    SUM(CASE WHEN player2 = winner THEN 1 ELSE 0 END) as p2_wins
FROM matches_2026
WHERE winner IS NOT NULL;

Expected:

roughly balanced p1/p2 win distribution.
2. Missing Rankings

Current state:

~30k matches missing rankings.

Likely causes:

juniors,
ITF players,
qualifiers,
unranked players,
incomplete name normalization.

Recommended strategy:

keep rows,
add explicit is_unranked features.
3. Player Name Normalization

Current issue:

abbreviated names still exist.

Examples:

Aahan A.
Abendroth I.

Impact:

H2H corruption,
ranking matching failures,
fatigue inaccuracies.

Priority:

medium.
4. H2H Feature Quality

Observation:

H2H ratio still falls back to 0.5 too often.

Interpretation:

sparse historical meetings,
limited signal quality.

Potential future actions:

reduce feature importance,
improve H2H matching,
confidence weighting.
🧠 Current ML Interpretation

The system is no longer:

ranking-only baseline

because:

engineered features now exist,
momentum distributions look healthy,
fatigue distributions appear realistic.

However:

the model reliability is NOT yet validated.

Current project phase:

scientific validation phase

not:

profit optimization phase
🎯 Immediate Next Step (Highest Priority)
Validate Target Integrity

This is the direct next step.

Goal:

verify that the target variable is statistically correct.

Why this matters:

all ML training depends entirely on target integrity.

If corrupted:

all training results become invalid,
accuracy becomes meaningless,
backtesting becomes fake.
Required Actions
Step 1

Run the validation SQL query.

Step 2

Verify:

player1 wins,
player2 wins,
overall balance.
Step 3

Trace winner creation pipeline:

Files to inspect:

collect_2026.py
collector.py
live_collector.py
database.py
Step 4

Fix any corruption before retraining.

🚀 After Target Validation

Only after target integrity is confirmed:

Phase 1
temporal split validation,
calibration,
feature importance.
Phase 2
bookmaker implied probabilities,
ROI tracking,
EV calculation.
Phase 3
model versioning,
drift monitoring,
failure analysis,
controlled retraining.
📌 Current Strategic Priority

The project should now focus on:

statistical correctness

NOT:

adding more features

The most important objective is now:

prove the system is scientifically reliable

before attempting:

real betting profitability