# Data truth and settlement policy

This repository is a paper-trading research prototype. It must not present model output as observed market or player data.

## Evidence classes

* **SOURCE_DATA** is a row retrieved from a named provider and retained with its retrieval timestamp.
* **DERIVED_DATA** is calculated only from source rows available at the decision timestamp.
* **MODEL_OUTPUT** is a probability or projection, not an observed result.
* **FORWARD_TEST** is used when a timestamped historical price or outcome is unavailable.
* **UNVERIFIED** data is retained only in the verification queue and is not eligible for settlement.

## Settlement gates

A simulated wager is eligible for historical settlement only when all of these are true:

1. The game is completed and has a verified final score (or verified player statistic for a prop).
2. The market price and decision timestamp are present in the source record.
3. The source was available before the decision timestamp.
4. The market-specific outcome can be calculated from observed data.

Historical player props are not included in the bundled nflverse game-level feed. The engine therefore flags and excludes player-prop signals rather than using a random draw, game total, or model probability as a fabricated result. Unverified Kalshi order books likewise belong in forward testing unless an archived, timestamped order book is present.

## Current repository limitations

The checked-in `data/` JSON exports are presentation fixtures, not proof that every listed row was independently retrieved during this run. They must not be described as verified historical odds unless their source snapshot and retrieval metadata are present. Before publishing a performance claim, run the loader against a fresh, versioned source snapshot and export the provenance record.

No real-money order is placed by this project. All trading is simulation only.
