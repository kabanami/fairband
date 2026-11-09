"""Mature Stable: the no-growth and stable-growth values (``design.md`` 6.11, spec 6.6, calibration
spec 5.10).

E is the normalized earnings, a total; both values come back in the unit of E. EPV is E ÷ r. The
stable-growth value is the reverse DCF of ``mature_growth`` on a path that grows at the terminal
growth in every year from the current earnings level (year 1 is E, with no (1 + g_t) factor), with
the reinvestment charge as the growth route applies it: at the return the charge's hold shapes,
which the route passes as 0 (spec 2026-11-09 6.3), so the return fades from the runway return in
year 1 to the terminal return in year N and the terminal, or none in years 1 to N−1 when the
charge is off. When the runway return is the terminal return and the charge is on, this is the
one-stage perpetuity E × (1 − g_t ÷ terminal ROIC) ÷ (r − g_t). When the margin flag fires,
E is scaled by the median operating margin ÷ the trailing operating margin, a proportional
approximation of margins at their norm.
"""

from fairband.engine.mature_growth import Charge, GrowthPath, value_at_belief


def mature_stable_values(e: float, charge: Charge, runway: int) -> tuple[float, float]:
    """``(epv, stable_growth)`` for normalized earnings ``e`` under ``charge`` over ``runway``
    years."""
    g_t = charge.g_t
    path = GrowthPath(e, (g_t, g_t), g_t, runway)
    return e / charge.r, value_at_belief(path, charge)


def normalize_for_margin(e: float, ttm_margin: float, median_margin: float, flagged: bool) -> float:
    """``e`` scaled to the median margin when flagged and both margins are positive, else ``e``."""
    if flagged and ttm_margin > 0 and median_margin > 0:
        return e * median_margin / ttm_margin
    return e
