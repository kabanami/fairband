"""Mature Stable: the no-growth and stable-growth values (``design.md`` 6.11, spec 6.6).

E is the normalized earnings, a total; both values come back in the unit of E. EPV is E ÷ r. The
stable-growth value is the perpetuity on the current earnings level, E × (1 − g_t ÷ terminal
ROIC) ÷ (r − g_t), with no (1 + g_t) factor: it is not the one-year-out terminal of Mature
Growth. When the margin flag fires, E is scaled by the median operating margin ÷ the trailing
operating margin, a proportional approximation of margins at their norm.
"""


def mature_stable_values(
    e: float, terminal_roic: float, r: float, g_t: float
) -> tuple[float, float]:
    """``(epv, stable_growth)`` for normalized earnings ``e``."""
    return e / r, e * (1 - g_t / terminal_roic) / (r - g_t)


def normalize_for_margin(e: float, ttm_margin: float, median_margin: float, flagged: bool) -> float:
    """``e`` scaled to the median margin when flagged and both margins are positive, else ``e``."""
    if flagged and ttm_margin > 0 and median_margin > 0:
        return e * median_margin / ttm_margin
    return e
