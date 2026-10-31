from fairband.vendors.scrub import scrub


def test_scrub_plain_and_encoded() -> None:
    assert (
        scrub("https://x/?apikey=SECRET123&sym=AAPL", ["SECRET123"])
        == "https://x/?apikey=<key>&sym=AAPL"
    )
    assert scrub("/public/user/T0K3N/stock", ["T0K3N"]) == "/public/user/<key>/stock"
    # A token with a reserved character: raw in a path, percent-encoded in a query string.
    assert scrub("/user/T0:K3N/x?t=T0%3AK3N", ["T0:K3N"]) == "/user/<key>/x?t=<key>"


def test_scrub_every_secret_longest_first() -> None:
    text = "a=SECRET123 b=SECRET123456 c=T0K3N"
    assert scrub(text, ["SECRET123", "SECRET123456", "T0K3N"]) == "a=<key> b=<key> c=<key>"


def test_scrub_ignores_empty_secrets() -> None:
    assert scrub("nothing to hide", ["", "SECRET123"]) == "nothing to hide"
    assert scrub("nothing to hide", []) == "nothing to hide"
