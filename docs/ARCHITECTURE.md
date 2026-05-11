Architecture
Data Flow
Sackmann CSV
    ↓
collector.py
    ↓
matches


TennisExplorer + Odds API
    ↓
live_collector.py
    ↓
matches_2026


matches + matches_2026
    ↓
feature_builder.py
    ↓
match_features
    ↓
predictor.py
    ↓
predictions
    ↓
reporter.py
Database Tables
Table	Purpose
matches	historical ATP matches
matches_2026	recent ATP/WTA matches
match_features	precomputed features
players_rankings	rankings history
predictions	model outputs
elo_ratings	ELO system
Design Decisions
SQLite

Chosen because:

lightweight,
simple deployment,
low VM resource usage.
Precomputed Features

Chosen because:

training was too slow,
VM RAM is limited.
Multi-Agent Architecture

Chosen because:

modularity,
maintainability,
future scalability.