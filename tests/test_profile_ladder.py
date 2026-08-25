import json

import pytest

import profile_ladder
from profile_ladder import LADDER, MAXIMUM_NAMES_PER_SECTOR, protocol_for, register


def test_ladder_orders_risk_in_one_direction_only():
    """A ladder whose dials disagree is not a ladder."""
    budgets = [LADDER[name]["maximum_equity_weight"] for name in ("conservador", "equilibrado", "arrojado")]
    counts = [LADDER[name]["top_assets"] for name in ("conservador", "equilibrado", "arrojado")]
    assert budgets == sorted(budgets), "equity budget must rise with the profile"
    assert counts == sorted(counts, reverse=True), "the basket must narrow as the profile takes more risk"


def test_issuer_cap_follows_the_declared_derivation():
    for name in LADDER:
        protocol = protocol_for(name, 2012, 2026)
        budget, count = protocol.maximum_equity_weight, protocol.top_assets
        expected = round(min(profile_ladder.MAXIMUM_ISSUER_CAP,
                             budget / count * profile_ladder.ISSUER_CAP_SLACK), 6)
        assert protocol.maximum_asset_weight == expected
        # The cap may never be so tight that the profile cannot reach its own
        # equity budget, which would quietly turn it into a cash book.
        assert protocol.maximum_asset_weight * count >= budget - 1e-9


def test_every_profile_carries_the_frozen_signal_and_sector_limit():
    for name in LADDER:
        protocol = protocol_for(name, 2012, 2026)
        assert protocol.factor == "triple_factor"
        assert protocol.maximum_names_per_sector == MAXIMUM_NAMES_PER_SECTOR
        # The ladder freezes selection, not the intra-year overlay.
        assert not protocol.apply_profile_risk_layer


def test_registration_records_no_performance_statistic(tmp_path):
    """A registration that reports a return is not a registration."""
    payload = register(tmp_path / "registration.json")
    text = json.dumps(payload, ensure_ascii=False).lower()
    for forbidden in ("observed_cagr", "realised_return", "backtest_return", "performance_result"):
        assert forbidden not in text
    assert payload["status"] == "registered_not_prospectively_validated"
    assert payload["selection_method"] == "declared, not searched"
    assert payload["intrayear_overlay"].startswith("not included")


def test_registration_hashes_every_declared_input(tmp_path):
    payload = register(tmp_path / "registration.json")
    assert set(payload["inputs"]) == set(profile_ladder.DATA_INPUTS)
    assert all(len(digest) == 64 for digest in payload["inputs"].values())
    assert set(payload["code"]) == {path.name for path in profile_ladder.CODE_INPUTS}
    written = json.loads((tmp_path / "registration.json").read_text(encoding="utf-8"))
    assert written["registration_sha256"] == payload["registration_sha256"]


def test_unknown_profile_is_rejected_rather_than_defaulted():
    with pytest.raises(KeyError):
        protocol_for("agressivo", 2012, 2026)
