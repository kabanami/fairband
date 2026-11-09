"""The stable-growth value summed by hand, for the engine tests to check against."""


def stable_dcf(
    e: float, runway_roic: float, terminal_roic: float, n: int, off: bool = False
) -> float:
    """The stable-growth value as the Mature Stable route charges it (spec 2026-11-09 6.3, a hold
    of 0): earnings grow 3% a year from ``e`` in year 1; year t pays out 1 − 3% ÷ its return,
    which fades in a straight line from the runway return, runway + (terminal − runway) × t ÷ n,
    so year n takes the terminal return (all of the earnings in years 1 to n − 1 when the charge
    is off); the terminal is year n's earnings × 1.03 × (1 − 3% ÷ terminal return) ÷ 6%;
    everything discounted at 9%."""
    value = 0.0
    for t in range(1, n + 1):
        ni = e * 1.03 ** (t - 1)
        ret = runway_roic + (terminal_roic - runway_roic) * t / n
        paid = ni if off and t < n else ni * (1 - 0.03 / ret)
        value += paid / 1.09**t
    final = e * 1.03 ** (n - 1)
    return value + final * 1.03 * (1 - 0.03 / terminal_roic) / 0.06 / 1.09**n
