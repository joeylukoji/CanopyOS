import numpy as np

from app.schemas import Metrics

GROUPS = {
    "vegetation": (4, 9, 17, 72),
    "hard_surface": (6, 11),
    "building": (0, 1, 25, 48),
    "open_ground": (13, 46, 91, 94),
}
COLORS = {
    "vegetation": (104, 196, 114),
    "hard_surface": (232, 163, 98),
    "building": (155, 155, 186),
    "open_ground": (214, 204, 135),
}
RECAPTURE = (
    "We couldn't confidently analyze this scene. "
    "Please capture a wider outdoor view with better lighting."
)


class SceneRejected(ValueError):
    pass


def green_score(vegetation: float, ground: float, trees: bool) -> int:
    return round(100 * min(1, max(0, 0.60 * vegetation + 0.25 * ground + 0.15 * trees)))


def priority(score: int) -> str:
    return "HIGH" if score < 35 else "MEDIUM" if score < 65 else "LOW"


def calculate_metrics(labels: np.ndarray) -> Metrics:
    if labels.ndim != 2 or labels.size == 0:
        raise SceneRejected(RECAPTURE)
    counts = {name: int(np.isin(labels, ids).sum()) for name, ids in GROUPS.items()}
    valid = sum(counts.values())
    # Demo quality gate: indoor evidence and low coverage require a new photograph.
    indoor = np.isin(labels, (3, 5, 7, 10, 15, 18, 19, 23, 35, 47, 50, 65, 71)).mean()
    outdoor = np.isin(labels, (2, 4, 6, 9, 11, 13, 72, 91, 94)).mean()
    if valid / labels.size < 0.25 or indoor > 0.20 or outdoor < 0.05:
        raise SceneRejected(RECAPTURE)
    ratios = {f"{name}_percentage": count / valid for name, count in counts.items()}
    trees = float(np.isin(labels, (4, 72)).sum()) / valid >= 0.01
    score = green_score(ratios["vegetation_percentage"], ratios["open_ground_percentage"], trees)
    return Metrics(
        **ratios,
        classified_coverage=valid / labels.size,
        tree_presence=trees,
        green_score=score,
        priority=priority(score),
    )
