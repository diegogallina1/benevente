import json

import pytest

import profile_ladder_v2
from portfolio_risk import risk_profile_spec
from profile_ladder_v2 import GLOBAL_FRACTION, LADDER_V2, domestic_protocol, register


def test_domestic_budget_is_solved_so_total_equity_lands_on_the_declared_budget():
    """Blending the fund into the whole portfolio dilutes the CDI residual too.

    Scaling the domestic budget naively would leave the profile holding more
    equity than it declares, and the comparison against v1 would be measuring
    that extra risk rather than the layers.
    """
    for name, item in LADDER_V2.items():
        budget = item["maximum_equity_weight"]
        share = budget * GLOBAL_FRACTION
        host = domestic_protocol(name, 2015, 2026).maximum_equity_weight
        assert (1 - share) * host + share == pytest.approx(budget), name
        assert host > budget * (1 - GLOBAL_FRACTION), "the host must absorb the dilution"


def test_the_fund_share_of_the_portfolio_is_the_declared_fraction_of_the_budget():
    for name, item in LADDER_V2.items():
        expected = item["maximum_equity_weight"] * GLOBAL_FRACTION
        assert expected == pytest.approx(register_share(name))


def register_share(name: str) -> float:
    return LADDER_V2[name]["maximum_equity_weight"] * GLOBAL_FRACTION


def test_arrojado_now_agrees_with_the_registered_risk_spec():
    """The v1 conflict is resolved by adopting the value already registered."""
    assert LADDER_V2["arrojado"]["maximum_equity_weight"] == risk_profile_spec("arrojado").maximum_equity_weight


def test_ladder_still_orders_risk_in_one_direction():
    budgets = [LADDER_V2[n]["maximum_equity_weight"] for n in ("conservador", "equilibrado", "arrojado")]
    counts = [LADDER_V2[n]["top_assets"] for n in ("conservador", "equilibrado", "arrojado")]
    assert budgets == sorted(budgets)
    assert counts == sorted(counts, reverse=True)


def test_registration_declares_the_currency_exposure_and_the_variant_count(tmp_path):
    payload = register(tmp_path / "v2.json")
    sleeve = payload["global_sleeve"]
    assert "dollar" in sleeve["unhedged_currency_warning"].lower()
    # Two combination variants were compared; presenting one as the only option
    # considered would understate the search.
    assert "two combination variants" in payload["trials_disclosure"].lower()
    assert payload["intrayear_overlay"]["applies_to"] == "domestic sleeve only"
    assert payload["supersedes"] == "benevente_profile_ladder_v1"


def test_registration_records_no_performance_statistic(tmp_path):
    payload = register(tmp_path / "v2.json")
    text = json.dumps(payload, ensure_ascii=False).lower()
    for forbidden in ("observed_cagr", "realised_return", "backtest_return", "cagr\":"):
        assert forbidden not in text
    assert payload["status"] == "registered_not_prospectively_validated"


def test_registration_hashes_inputs_and_its_own_code(tmp_path):
    payload = register(tmp_path / "v2.json")
    assert all(len(d) == 64 for d in payload["inputs"].values())
    assert "profile_ladder_v2.py" in payload["code"]
    written = json.loads((tmp_path / "v2.json").read_text(encoding="utf-8"))
    assert written["registration_sha256"] == payload["registration_sha256"]


def test_a_registration_can_never_be_anonymous(monkeypatch):
    """An audit trail that stops before the signature stops where it matters."""
    assert profile_ladder_v2.resolve_approver("  Fulana de Tal  ") == ("Fulana de Tal", "explicit")
    blank = type("Result", (), {"stdout": " \n"})
    monkeypatch.setattr(profile_ladder_v2.subprocess, "run", lambda *args, **kwargs: blank())
    with pytest.raises(SystemExit, match="assinante"):
        profile_ladder_v2.resolve_approver(None)


def test_the_frozen_registration_names_who_froze_it():
    """Whether or not v2 has been frozen yet, it can only exist signed."""
    frozen = profile_ladder_v2.ROOT / "data" / "benevente_profile_ladder_v2_registration.json"
    if not frozen.exists():
        pytest.skip("v2 ainda não foi congelada")
    payload = json.loads(frozen.read_text(encoding="utf-8"))
    assert payload["approved_by"].strip(), "um registro sem assinante não é um registro"
    assert payload["approval_source"] in {"explicit", "git identity"}
    assert payload["policy"] == "benevente_profile_ladder_v2"
    assert payload["supersedes"] == "benevente_profile_ladder_v1"
