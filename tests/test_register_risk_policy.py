import json

from register_risk_policy import register


def test_registration_is_hashed_and_starts_after_design_date(tmp_path) -> None:
    target = tmp_path / "registration.json"
    payload = register(target)
    assert payload["status"] == "registered_not_prospectively_validated"
    assert payload["confirmatory_sample_starts"] == "first B3 trading session of 2027"
    assert len(payload["registration_sha256"]) == 64
    assert json.loads(target.read_text(encoding="utf-8"))["registration_sha256"] == payload["registration_sha256"]
