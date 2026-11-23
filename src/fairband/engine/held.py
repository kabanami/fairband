"""The state of a held reviewed value (spec 2026-11-23 held reviewed value, 5.3).

A reviewed value is held until the next made review. It is expired when its window's date has
passed, as any value is, and expired early while one of three reasons holds. Reason 3 is the
size test this module starts with: computed again by a refresh, the review gives a value outside
the held value's fair band, or gives none.
"""

# The start of the refusal of a reading that failed (``refresh.reviews``): such a reading is no
# reason, and the last good reading stands.
READING_FAILED = "review failed"


def reading_outside(
    value: float | None,
    reading_value: float | None,
    reading_refusal: str | None,
    band: tuple[float, float],
) -> bool:
    """Whether the newest good reading is reason 3 against the held ``value``: its value ÷ the
    held value is under ``band``'s low or over its high, the fair band in force, or the reading
    refuses on the data. Both values are a share on the same basis and in US dollars. A held
    review with no value above zero, and a company with no reading yet, give no reason."""
    if value is None or value <= 0:
        return False
    if reading_value is None:
        return reading_refusal is not None
    low, high = band
    return not low <= reading_value / value <= high
