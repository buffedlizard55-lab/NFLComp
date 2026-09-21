"""Market settlement helpers based only on observed game results.

NFL spread convention in the bundled source is the home-team handicap:
negative means the home team is favored. Therefore home ATS margin is
``home_score - away_score + spread_line``.
"""


def settle_spread(home_margin: float, home_spread: float, side: str) -> float:
    """Return 1.0 (win), 0.5 (push), or 0.0 (loss) for a spread side."""
    if side not in {"home", "away"}:
        raise ValueError(f"Unsupported spread side: {side}")
    adjusted_margin = home_margin + home_spread
    if adjusted_margin == 0:
        return 0.5
    home_covered = adjusted_margin > 0
    return 1.0 if (home_covered == (side == "home")) else 0.0


def settle_total(actual_total: float, total_line: float, side: str) -> float:
    """Return 1.0 (win), 0.5 (push), or 0.0 (loss) for a total side."""
    if side not in {"over", "under"}:
        raise ValueError(f"Unsupported total side: {side}")
    if actual_total == total_line:
        return 0.5
    went_over = actual_total > total_line
    return 1.0 if (went_over == (side == "over")) else 0.0
