"""Engine fixtures: the policy, the universe deciles and the companies of
``support.engine_companies``."""

import pytest
from support import engine_companies

from fairband.engine.classifier import Deciles
from fairband.engine.route import CompanyInputs
from fairband.policy import Policy, load_policy


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
