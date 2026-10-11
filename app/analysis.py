from __future__ import annotations

from typing import Any

import pandas as pd

BAND_EDGES = [-1, 0, 499, 2000, float("inf")]
BAND_LABELS = ["free", "under_500", "500_2000", "over_2000"]


def affordability_index(cost: int | None) -> float:
    """0 (expensive) .. 1 (free). Unknown cost -> 0.5. Log-ish scale capped at $8k."""
    if cost is None:
        return 0.5
    if cost <= 0:
        return 1.0
    return round(max(0.0, 1.0 - min(cost, 8000) / 8000) ** 1.5, 3)


def density_grid(frame: pd.DataFrame, cell_deg: float = 2.0) -> list[dict[str, Any]]:
    """Count opportunities per lat/lng cell (equal-angle grid) for the density layer."""
    cells = (
        frame.assign(
            cy=(frame["lat"] // cell_deg).astype(int),
            cx=(frame["lng"] // cell_deg).astype(int),
        )
        .groupby(["cy", "cx"])
        .agg(count=("id", "size"), mean_score=("compatibility", "mean"))
        .reset_index()
        .sort_values("count", ascending=False)
    )
    return [
        {
            "lat": (r.cy + 0.5) * cell_deg,
            "lng": (r.cx + 0.5) * cell_deg,
            "count": int(r.count),
            "mean_score": round(float(r.mean_score), 1),
        }
        for r in cells.itertuples()
    ]


def analyze(ranked: list[dict[str, Any]]) -> dict[str, Any]:
    if not ranked:
        return {
            "count": 0, "mean_score": 0, "median_cost": None, "travel_share": 0,
            "eligible_share": 0, "by_type": {}, "by_sport": {}, "by_country": {},
            "score_by_type": {}, "score_histogram": {}, "affordability_bands": {},
            "density": [], "top_quartile_cutoff": 0,
        }

    frame = pd.DataFrame(ranked)
    costs = frame["cost_usd"].dropna()
    known = frame["cost_usd"].astype("float").fillna(-2)
    bands = pd.cut(known[known >= -1], BAND_EDGES, labels=BAND_LABELS).value_counts()

    hist = pd.cut(frame["compatibility"], [0, 40, 55, 70, 85, 100], include_lowest=True)
    hist_counts = hist.value_counts().sort_index()

    return {
        "count": int(len(frame)),
        "mean_score": round(float(frame["compatibility"].mean()), 1),
        "top_quartile_cutoff": int(frame["compatibility"].quantile(0.75)),
        "median_cost": None if costs.empty else int(costs.median()),
        "unknown_cost": int(frame["cost_usd"].isna().sum()),
        "travel_share": round(float(frame["is_travel"].mean()) * 100, 1),
        "eligible_share": round(float(frame["eligible"].mean()) * 100, 1),
        "by_type": {str(k): int(v) for k, v in frame["type"].value_counts().items()},
        "by_sport": {str(k): int(v) for k, v in frame["sport"].value_counts().head(8).items()},
        "by_country": {str(k): int(v) for k, v in frame["country"].value_counts().head(8).items()},
        "score_by_type": {
            str(k): round(float(v), 1)
            for k, v in frame.groupby("type")["compatibility"].mean().sort_values(ascending=False).items()
        },
        "score_histogram": {f"{int(i.left) + 1 if i.left > 0 else 0}-{int(i.right)}": int(c) for i, c in hist_counts.items()},
        "affordability_bands": {k: int(bands.get(k, 0)) for k in BAND_LABELS},
        "density": density_grid(frame),
    }
