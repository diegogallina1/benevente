"""Freeze the profile risk policy before a genuinely prospective sample."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import argparse
import hashlib
import json

from benevente2_event_risk import RiskOverlayConfig
from corporate_action_reconciliation import file_sha256
from portfolio_risk import PROFILE_SPECS
from profile_intrayear_risk import FIXED_OVERLAY


ROOT = Path(__file__).resolve().parent


def _hash_payload(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def register(output: str | Path) -> dict:
    code_files = [
        ROOT / "annual_walk_forward.py", ROOT / "portfolio_risk.py",
        ROOT / "profile_intrayear_risk.py", ROOT / "benevente2_event_risk.py",
    ]
    data_files = [
        ROOT / "data" / "fundamentals_b3_cvm_full_2012_2025.csv",
        ROOT / "data" / "b3_historical_universes_2012_2025.csv",
        ROOT / "data" / "b3_historical_cvm_ticker_map_2012_2025.csv",
        ROOT / "data" / "prices_b3_total_return_full_2011_2025_manifest.json",
        ROOT / "data" / "b3_primary_events_2011_2025_manifest.json",
    ]
    overlay: RiskOverlayConfig = FIXED_OVERLAY
    payload = {
        "policy": "benevente_profile_risk_v1",
        "status": "registered_not_prospectively_validated",
        "registered_at": datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(),
        "confirmatory_sample_starts": "first B3 trading session of 2027",
        "2026_remainder_status": "operational pilot only; excluded from confirmatory evidence",
        "annual_selection": {
            "signal_family": "triple_factor",
            "minimum_equity_positions": 5,
            "review_frequency": "annual",
            "selection_and_risk_are_separate": True,
        },
        "profiles": {name: spec.__dict__ for name, spec in PROFILE_SPECS.items()},
        "intrayear_overlay": {
            "observable_market": "Ibovespa total-return series",
            "signal_lag_sessions": 1,
            "alert_drawdown": overlay.alert_drawdown,
            "severe_drawdown": overlay.severe_drawdown,
            "alert_volatility": overlay.alert_volatility,
            "severe_volatility": overlay.severe_volatility,
            "recovery_days": overlay.recovery_days,
            "volatility_window": overlay.volatility_window,
            "peak_window": overlay.peak_window,
            "cost_bps_per_exposure_change": overlay.cost_bps,
            "changes_assets_intrayear": False,
        },
        "confirmatory_reporting": [
            "return after execution costs and Brazilian taxes",
            "maximum drawdown and annualized volatility",
            "turnover and time below the profile target exposure",
            "CDI, Ibovespa total return, BOVA11 and independent MVO comparators",
            "every deviation, missing datum and human override",
        ],
        "non_negotiable_gates": {
            "complete_primary_event_reconciliation": True,
            "minimum_positions_respected": True,
            "no_parameter_change_after_sample_start": True,
            "tax_model_completed_before_confirmatory_scoring": True,
            "at_least_three_complete_annual_decisions_before_performance_claim": True,
        },
        "code_sha256": {path.name: file_sha256(path) for path in code_files},
        "input_sha256": {path.name: file_sha256(path) for path in data_files if path.exists()},
    }
    payload["registration_sha256"] = _hash_payload(payload)
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze the Benevente profile risk policy.")
    parser.add_argument("--output", default="data/benevente_profile_risk_v1_registration.json")
    args = parser.parse_args()
    print(json.dumps(register(args.output), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
