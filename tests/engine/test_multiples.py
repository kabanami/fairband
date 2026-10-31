from fairband.engine.multiples import epv, growth_share, multiples


def test_multiples_and_epv() -> None:
    m = multiples(100.0, 5.0, 4.0, 0.0)
    assert m.pe_reported == 20.0 and m.pe_clean == 25.0 and m.pe_forward is None
    assert epv(9.0, 0.09) == 100.0 and growth_share(100.0, 400.0) == 0.75


def test_missing_or_negative_eps_has_no_multiple() -> None:
    m = multiples(100.0, None, -2.0, 8.0)
    assert m.pe_reported is None and m.pe_clean is None and m.pe_forward == 12.5
