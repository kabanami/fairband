"""Key scrubbing: no vendor key leaves ``fairband.vendors`` in a URL, a log line or a message."""

from collections.abc import Iterable
from urllib.parse import quote

KEY = "<key>"


def scrub(text: str, secrets: Iterable[str]) -> str:
    """``text`` with each non-empty secret, raw or percent-encoded, replaced by ``<key>``.

    The longest forms go first, so a secret that contains another is replaced whole.
    """
    forms = {form for secret in secrets if secret for form in (secret, quote(secret, safe=""))}
    for form in sorted(forms, key=len, reverse=True):
        text = text.replace(form, KEY)
    return text
