"""The stable-growth value summed by hand, for the engine tests to check against."""


def stable_dcf(
    e: float, runway_roic: float, terminal_roic: float, n: int, off: bool = False
) -> float:
    """The stable-growth value as the growth route charges it: earnings grow 3% a year from ``e``
    in year 1; each year pays out 1 − 3% ÷ the return it is charged at, the runway return to year
    n − 1 (all of the earnings when the charge is off) and the terminal return in year n; the
    terminal is year n's earnings × 1.03 × (1 − 3% ÷ terminal return) ÷ 6%; everything discounted
    at 9%."""
    value = 0.0
    for t in range(1, n + 1):
        ni = e * 1.03 ** (t - 1)
        if t < n:
            paid = ni if off else ni * (1 - 0.03 / runway_roic)
        else:
            paid = ni * (1 - 0.03 / terminal_roic)
        value += paid / 1.09**t
    final = e * 1.03 ** (n - 1)
    return value + final * 1.03 * (1 - 0.03 / terminal_roic) / 0.06 / 1.09**n
