from fairband.engine.multiples import epv, growth_share, multiples
from fairband.engine.route_steps import multiples_at


def test_multiples_and_epv() -> None:
    m = multiples(100.0, 5.0, 4.0, 0.0, 0.0)
    assert m.pe_reported == 20.0 and m.pe_clean == 25.0 and m.pe_forward is None
    assert m.pe_forward_after_sbc is None
    assert epv(9.0, 0.09) == 100.0 and growth_share(100.0, 400.0) == 0.75


def test_missing_or_negative_eps_has_no_multiple() -> None:
    m = multiples(100.0, None, -2.0, 8.0, None)
    assert m.pe_reported is None and m.pe_clean is None and m.pe_forward == 12.5
    assert m.pe_forward_after_sbc is None


def test_the_forward_multiple_after_stock_pay_stands_beside_the_plain_one() -> None:
    """Method 5.9 under 1.10: the forward P/E is the price over the analysts' EPS as they state
    it, and the second forward P/E the price over that EPS less the stock-pay charge; a charged
    EPS at or below zero has none, the plain one standing."""
    m = multiples(100.0, None, None, 8.0, 6.4)
    assert (m.pe_forward, m.pe_forward_after_sbc) == (12.5, 15.625)
    lost = multiples(100.0, None, None, 8.0, -1.0)
    assert (lost.pe_forward, lost.pe_forward_after_sbc) == (12.5, None)


def test_an_eps_record_of_an_earlier_method_has_no_second_forward_multiple() -> None:
    """A record stored before 1.10 holds no ``forward_after_sbc``: read at a price, it gives the
    three multiples it gave and none after stock pay."""
    earlier = {"reported": 5.0, "clean": 4.0, "forward": 8.0}
    assert multiples_at(100.0, earlier) == {
        "pe_reported": 20.0,
        "pe_clean": 25.0,
        "pe_forward": 12.5,
        "pe_forward_after_sbc": None,
    }
    now = {**earlier, "forward_after_sbc": 6.4}
    assert multiples_at(100.0, now)["pe_forward_after_sbc"] == 15.625
