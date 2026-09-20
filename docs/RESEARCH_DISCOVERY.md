# Research discovery workflow

`engine/research_discovery.py` generates auditable candidate hypotheses from a source snapshot. It does not manufacture a strategy result, odds, fill, or edge.

```python
from engine.research_discovery import discover_candidates
candidates = discover_candidates(rows, source_id="nflverse-games-snapshot", retrieved_at="2026-09-20T00:00:00Z")
```

Each candidate includes the required fields, fields actually present, missing fields, source ID, row count, discovery time, and a `performance_claim` set to `null`. `BLOCKED_MISSING_DATA` candidates remain research queue items. `READY_FOR_TEST` only means the schema is available; it is not evidence of predictiveness.

A candidate can only become a backtest after the point-in-time data and timestamped market-price checks pass. If historical prices or market-specific outcomes are unavailable, it must be labeled `FORWARD_TEST`.
