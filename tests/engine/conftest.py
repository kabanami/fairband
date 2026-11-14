"""Engine fixtures: the policy, the universe deciles and the companies of
``support.engine_companies``; the two mature companies past the guards, as their routes read them,
and ``with_overrides``, which puts an agent's applied overrides on such a context."""

from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, date, datetime

import pytest
from support import engine_companies

from fairband.engine.classifier import Deciles
from fairband.engine.overrides import Override, OverrideTag
from fairband.engine.route import CompanyInputs
from fairband.engine.route_steps import Context
from fairband.policy import Policy, load_policy

TODAY = date(2026, 10, 31)  # the day the engine's test companies are valued
NOW = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)  # the time the fixtures' overrides are made

WithOverrides = Callable[[Context, Mapping[OverrideTag, float | str]], Context]


@pytest.fixture
def policy() -> Policy:
    return load_policy()


@pytest.fixture
def deciles() -> Deciles:
    return engine_companies.universe_deciles()


@pytest.fixture
def mg_inputs() -> CompanyInputs:
    return engine_companies.mature_growth_inputs()


@pytest.fixture
def ms_inputs() -> CompanyInputs:
    return engine_companies.mature_stable_inputs()


@pytest.fixture
def young_growth_inputs() -> CompanyInputs:
    return engine_companies.young_growth_inputs()


@pytest.fixture
def high_growth_inputs() -> CompanyInputs:
    return engine_companies.high_growth_inputs()


@pytest.fixture
def decline_inputs() -> CompanyInputs:
    return engine_companies.decline_inputs()


@pytest.fixture
def start_up_inputs() -> CompanyInputs:
    return engine_companies.start_up_inputs()


def _context(i: CompanyInputs, policy: Policy) -> Context:
    """``i`` past the guards, as ``route.value_company`` builds the context its route reads."""
    assert i.trailing is not None and i.price is not None and i.shares_diluted is not None
    return Context(i, i.trailing, i.price, i.shares_diluted, i.shares_diluted, policy, TODAY)


@pytest.fixture
def mg_context(mg_inputs: CompanyInputs, policy: Policy) -> Context:
    """MGCO past the guards: $150 on 1 bn shares, an NTM consensus of 5.90 a share that includes
    stock compensation, a non-recurring gap of 0.05."""
    return _context(mg_inputs, policy)


@pytest.fixture
def ms_context(ms_inputs: CompanyInputs, policy: Policy) -> Context:
    """MSCO past the guards: $40 on 1 bn shares, a non-recurring gap of 0.10, a flat 20% margin."""
    return _context(ms_inputs, policy)


@pytest.fixture
def with_overrides() -> WithOverrides:
    """A context under an agent's applied overrides of ``values``, by tag."""

    def judged(c: Context, values: Mapping[OverrideTag, float | str]) -> Context:
        overrides = {
            tag: Override(1, tag, value, "agent", "claude-opus-5-5", NOW, "mid-cycle")
            for tag, value in values.items()
        }
        return replace(c, overrides=overrides)

    return judged
