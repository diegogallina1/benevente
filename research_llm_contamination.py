"""Measure how much a language model's memory of the future is worth.

Any backtest that asks a language model to judge an asset in January 2019 has a
problem the model cannot opt out of: it was trained on text written after 2019.
Asked about PETR4, it does not only read the fundamentals in the prompt, it also
remembers what happened. Every published claim of alpha from an LLM screening
historical assets is exposed to this, and the usual defence is a sentence saying
it was considered.

This module measures it instead, by running the identical decision twice.

``named``
    The model sees the ticker and the sector alongside the dated fundamentals.
    It can recognise the company.
``anonymised``
    The model sees only the dated fundamentals, with assets labelled A1, A2 and
    so on, and no sector. There is nothing to recognise.

The gap between the two arms is the contamination, expressed in return. If the
named arm wins, the advantage came from memory rather than from analysis, and
the honest reading of any LLM backtest on this period is the anonymised number.

A third arm answers the architecture question separately.

``monolithic``
    The model is asked for portfolio weights directly, the way a naive
    integration would. Its weights are used as given, and every constraint
    breach is recorded. This is the baseline that the decoupled design — model
    emits a bounded confidence score, convex solver decides weights — has to
    beat on turnover and on feasibility, not only on return.

Nothing here lets the model choose a weight in the decoupled arms: its score
enters the optimiser as a tilt on expected return, bounded to [-1, 1], and the
optimiser still enforces the equity cap, the issuer cap and the turnover
penalty. Every raw response is archived so a reviewer can audit what was asked
and what came back.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import time

import numpy as np
import pandas as pd

from advisor import snapshots_from_frame
from annual_decision_evidence import load_decision_evidence
from annual_walk_forward import (
    AnnualWalkForwardConfig,
    AnnualWalkForwardEngine,
    _execution_cost_brl,
    _liquidity_map,
    _price_column_for_ticker,
    _recent_market_sessions,
    realised_returns_with_delisting,
)
from config import SystemConfig
from optimizer import MeanVarianceOptimizer
from total_return_adapter import load_total_return_export


GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
SCORE_SCHEMA = {
    "type": "object",
    "properties": {
        "scores": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "confidence": {"type": "number"},
                    "reason": {"type": "string"},
                },
                "required": ["id", "confidence"],
            },
        }
    },
    "required": ["scores"],
}
WEIGHT_SCHEMA = {
    "type": "object",
    "properties": {
        "weights": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "string"}, "weight": {"type": "number"}},
                "required": ["id", "weight"],
            },
        }
    },
    "required": ["weights"],
}

DECOUPLED_INSTRUCTION = (
    "You are a disciplined equity analyst. For each asset below you receive only accounting figures that were "
    "publicly available on the decision date. Return a confidence score in [-1.0, 1.0] for each asset id, where "
    "-1.0 means clearly unattractive and 1.0 means clearly attractive on these figures alone. "
    "You must not return portfolio weights. You must not use any knowledge of what happened after the decision date."
)
MONOLITHIC_INSTRUCTION = (
    "You are a portfolio manager. Using only the accounting figures below, return portfolio weights that sum to "
    "1.0 across the asset ids given, with no weight above {cap:.3f} and no negative weight. "
    "Return only the weights."
)


def _load_env(path: Path) -> None:
    """Read KEY=value pairs from a local env file without extra dependencies."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def _cache_key(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:32]


def call_gemini(prompt: str, schema: dict, model: str, cache_dir: Path,
                api_key: str, temperature: float = 0.0, attempts: int = 4,
                quota_backoff_seconds: int = 45) -> dict:
    """One structured call, cached on disk so a rerun costs nothing.

    Temperature zero and an archived response are what make the experiment
    reproducible; a study whose inputs cannot be re-read is not evidence.
    """
    import requests

    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json",
                             "responseSchema": schema, "temperature": temperature},
    }
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / f"{_cache_key({'p': prompt, 's': schema, 'm': model, 't': temperature})}.json"
    if cached.exists():
        return json.loads(cached.read_text(encoding="utf-8"))
    last_error = ""
    for attempt in range(attempts):
        try:
            response = requests.post(GEMINI_URL.format(model=model), params={"key": api_key},
                                     json=body, timeout=180)
            if response.status_code == 200:
                payload = response.json()
                text = payload["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(text)
                cached.write_text(json.dumps({"raw": payload, "parsed": parsed}, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
                return {"raw": payload, "parsed": parsed}
            last_error = f"HTTP {response.status_code}: {response.text[:300]}"
            if response.status_code == 429:
                # A quota refusal is not a transient network blip. Backing off in
                # seconds just burns the remaining attempts; the run is resumable
                # because every completed call is cached, so wait properly.
                delay = quota_backoff_seconds * (attempt + 1)
                print(f"  cota excedida, aguardando {delay}s antes de tentar de novo")
                time.sleep(delay)
                continue
        except Exception as exc:  # network and parsing failures are both retryable
            last_error = f"{type(exc).__name__}: {exc}"
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Gemini call failed after {attempts} attempts. {last_error}")


FUNDAMENTAL_FIELDS = ("price_to_earnings", "price_to_book", "ev_to_ebit", "free_cash_flow_yield",
                      "roe", "roic", "debt_to_ebitda", "interest_coverage", "operating_margin",
                      "market_cap_brl", "average_daily_value_brl")


def build_prompt(screen: pd.DataFrame, decision: pd.Timestamp, arm: str, cap: float) -> tuple[str, dict[str, str]]:
    """Render the eligible universe for one arm, and the id mapping used."""
    assets: list[dict] = []
    mapping: dict[str, str] = {}
    for position, row in enumerate(screen.itertuples(index=False), start=1):
        identifier = row.ticker if arm == "named" else f"A{position}"
        mapping[identifier] = row.ticker
        record: dict[str, object] = {"id": identifier}
        if arm == "named":
            record["ticker"] = row.ticker
            record["sector"] = getattr(row, "sector", None)
        for field in FUNDAMENTAL_FIELDS:
            value = getattr(row, field, None)
            if value is not None and pd.notna(value):
                record[field] = round(float(value), 6)
        record["as_of_date"] = str(getattr(row, "as_of_date", ""))[:10]
        assets.append(record)
    instruction = MONOLITHIC_INSTRUCTION.format(cap=cap) if arm == "monolithic" else DECOUPLED_INSTRUCTION
    header = (f"{instruction}\n\nDecision date: {decision.date().isoformat()}. "
              f"{len(assets)} assets. Figures are in Brazilian reais and were filed before the decision date.\n")
    return header + json.dumps({"assets": assets}, ensure_ascii=False), mapping


def eligible_screen(engine: AnnualWalkForwardEngine, protocol: AnnualWalkForwardConfig,
                    decision: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """The same dated screen the published strategy uses, reused verbatim."""
    from fundamentals import snapshots_available_on

    known = list(snapshots_available_on(engine.snapshots, decision).values())
    if engine.decision_evidence is not None:
        permitted = engine.decision_evidence.allowed(decision)
        known = [item for item in known if item.ticker in permitted]
    prior = engine.prices.loc[engine.prices.index < decision]
    columns = {item.ticker: _price_column_for_ticker(item.ticker, prior.columns) for item in known}
    sessions = _recent_market_sessions(engine.prices, decision, protocol.minimum_history_days)
    if len(sessions) < protocol.minimum_history_days + 1:
        return pd.DataFrame(), pd.DataFrame(), []
    complete = [ticker for ticker, column in columns.items()
                if column is not None and prior.loc[sessions, column].notna().all()]
    known = [item for item in known if item.ticker in complete]
    if not known:
        return pd.DataFrame(), pd.DataFrame(), []
    source_columns = [columns[ticker] for ticker in complete]
    history = prior.loc[sessions, [*source_columns, "TITULO_CDI"]].rename(
        columns={columns[ticker]: ticker for ticker in complete}).pct_change().dropna()
    screen = engine.triple_factor_screen(known, history.tail(protocol.minimum_history_days), decision, protocol)
    return screen[screen.eligible].copy(), history, complete


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure LLM temporal contamination in a dated stock screen.")
    parser.add_argument("--prices", default="data/prices_b3_total_return_full_2011_2025.csv")
    parser.add_argument("--total-return-manifest", default="data/prices_b3_total_return_full_2011_2025_manifest.json")
    parser.add_argument("--fundamentals", default="data/fundamentals_b3_cvm_full_2013_2025_v2.csv")
    parser.add_argument("--universe", default="data/b3_historical_universes.csv")
    parser.add_argument("--mapping", default="data/b3_historical_cvm_ticker_map.csv")
    parser.add_argument("--benchmarks", default="data/benchmarks_market_2011_2025.csv")
    parser.add_argument("--start-year", type=int, default=2013)
    parser.add_argument("--end-year", type=int, default=2026)
    # A pinned name, never an alias. "gemini-flash-latest" would silently change
    # the model under the experiment and make the archived responses
    # unreproducible. Repeating the study across models with different training
    # cutoffs is the natural extension: contamination should grow with recency.
    parser.add_argument("--model", default="gemini-3.1-flash-lite")
    parser.add_argument("--equity-cap", type=float, default=.55)
    parser.add_argument("--issuer-cap", type=float, default=.176)
    parser.add_argument("--top-assets", type=int, default=5)
    parser.add_argument("--signal-influence", type=float, default=.30)
    parser.add_argument("--env-file", default=".env.local")
    parser.add_argument("--cache-dir", default="work/llm_contamination")
    parser.add_argument("--output", default="artifacts/llm_contamination")
    parser.add_argument("--arms", default="named,anonymised,monolithic")
    parser.add_argument("--pace-seconds", type=float, default=5.0,
                        help="Delay between calls. The free tier caps requests per minute as well as per day.")
    args = parser.parse_args()

    _load_env(Path(args.env_file))
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise SystemExit("Set GEMINI_API_KEY (or GOOGLE_API_KEY), for example in .env.local.")

    prices, _ = load_total_return_export(args.prices, args.total_return_manifest)
    fundamentals = pd.read_csv(args.fundamentals, parse_dates=["as_of_date", "available_date"])
    evidence, _ = load_decision_evidence(args.universe, args.mapping)
    benchmarks = pd.read_csv(args.benchmarks, parse_dates=["date"]).set_index("date")
    engine = AnnualWalkForwardEngine(prices.set_index("date"), snapshots_from_frame(fundamentals),
                                     SystemConfig(), evidence, benchmarks)
    protocol = AnnualWalkForwardConfig(args.start_year, args.end_year, top_assets=args.top_assets,
                                       maximum_equity_weight=args.equity_cap,
                                       maximum_asset_weight=args.issuer_cap, factor="triple_factor")
    arms = [item.strip() for item in args.arms.split(",") if item.strip()]
    cache = Path(args.cache_dir)
    rows: list[dict] = []
    violations: list[dict] = []

    for year in range(args.start_year, args.end_year):
        decision = next((date for date in engine.prices.index if date.year == year), None)
        following = next((date for date in engine.prices.index if date.year == year + 1), None)
        if decision is None:
            continue
        end = following if following is not None else engine.prices.index[-1] + pd.Timedelta(days=1)
        screen, history, complete = eligible_screen(engine, protocol, decision)
        if screen.empty or len(screen) < 2:
            continue
        realised_slice = engine.prices.loc[(engine.prices.index >= decision) & (engine.prices.index < end)]
        available = [ticker for ticker in complete if _price_column_for_ticker(ticker, realised_slice.columns)]
        renamed = realised_slice[[_price_column_for_ticker(ticker, realised_slice.columns) for ticker in available]
                                 + ["TITULO_CDI"]].rename(
            columns={_price_column_for_ticker(ticker, realised_slice.columns): ticker for ticker in available})
        if len(renamed) < 2:
            continue
        realised = realised_returns_with_delisting(renamed)
        growth = (1 + realised).prod()
        liquidity = _liquidity_map(screen)
        planner = replace(SystemConfig(), max_asset_weight=args.issuer_cap, rolling_window_days=protocol.minimum_history_days)

        for arm in arms:
            prompt, mapping = build_prompt(screen, decision, arm, args.issuer_cap)
            schema = WEIGHT_SCHEMA if arm == "monolithic" else SCORE_SCHEMA
            try:
                response = call_gemini(prompt, schema, args.model, cache / arm, api_key)
                # The free tier allows fifteen requests per minute. Pacing here
                # is cheaper than discovering the limit through a refusal.
                time.sleep(args.pace_seconds)
            except Exception as exc:
                violations.append({"decision_year": year, "arm": arm, "issue": "call_failed", "detail": str(exc)[:200]})
                continue
            parsed = response["parsed"]
            columns = [ticker for ticker in screen.ticker if ticker in history.columns]
            if arm == "monolithic":
                raw = {mapping.get(str(item.get("id")), str(item.get("id"))): float(item.get("weight", 0.0))
                       for item in parsed.get("weights", [])}
                unknown = [key for key in raw if key not in columns]
                weights = pd.Series({ticker: max(0.0, raw.get(ticker, 0.0)) for ticker in columns})
                total = float(weights.sum())
                violations.append({
                    "decision_year": year, "arm": arm, "issue": "constraint_audit",
                    "sum_before_normalisation": total,
                    "weights_above_cap": int((weights > args.issuer_cap + 1e-9).sum()),
                    "negative_weights": int(sum(1 for value in raw.values() if value < 0)),
                    "unknown_ids": len(unknown),
                    "missing_ids": int(len(columns) - len([t for t in columns if t in raw])),
                })
                if total <= 0:
                    continue
                # Used as given, only renormalised, because the point of this arm
                # is to show what happens when the model is trusted with weights.
                target = (weights / total * args.equity_cap).reindex(realised.columns, fill_value=0.0)
                target["TITULO_CDI"] = 1 - float(target.drop(labels="TITULO_CDI").sum())
            else:
                scores = {mapping.get(str(item.get("id")), str(item.get("id"))): float(item.get("confidence", 0.0))
                          for item in parsed.get("scores", [])}
                bounded = {ticker: float(np.clip(scores.get(ticker, 0.0), -1.0, 1.0)) for ticker in columns}
                ranked = sorted(bounded.items(), key=lambda item: -item[1])[:args.top_assets]
                selected = [ticker for ticker, _ in ranked]
                optimiser_columns = [*selected, "TITULO_CDI"]
                target = MeanVarianceOptimizer(planner).optimize(
                    history.loc[:, optimiser_columns].tail(protocol.minimum_history_days),
                    {**{ticker: bounded[ticker] for ticker in selected}, "TITULO_CDI": 0.0},
                    equity_cap=args.equity_cap, signal_influence=args.signal_influence,
                    eligible_assets=set(selected),
                ).reindex(realised.columns, fill_value=0.0)
            gross = float((target * growth.reindex(target.index).fillna(1.0)).sum() - 1)
            cost = _execution_cost_brl(target, pd.Series(0.0, index=target.index), 1_000_000.0, liquidity) / 1_000_000.0
            rows.append({
                "decision_year": year, "arm": arm, "eligible_assets": int(len(screen)),
                "equity_weight": float(target.drop(labels="TITULO_CDI").sum()),
                "gross_return": gross, "cost_rate": cost, "net_return": gross - cost,
                "cdi_net_return": float(growth.get("TITULO_CDI", 1.0) - 1),
                "holdings": " | ".join(f"{ticker}:{weight:.1%}" for ticker, weight in
                                       target.drop(labels="TITULO_CDI").sort_values(ascending=False).items()
                                       if weight > 1e-6),
            })
        print(f"{year}: {len(screen)} elegíveis, braços concluídos")

    results = pd.DataFrame(rows)
    if results.empty:
        raise SystemExit("No arm produced an evaluable year. Check the API key and the screen.")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    results.to_csv(output / "annual_by_arm.csv", index=False)
    pd.DataFrame(violations).to_csv(output / "constraint_audit.csv", index=False)

    def cagr(series: pd.Series) -> float:
        clean = series.dropna()
        return float((1 + clean).prod() ** (1 / len(clean)) - 1) if len(clean) else float("nan")

    per_arm = {}
    for arm, frame in results.groupby("arm"):
        frame = frame.sort_values("decision_year")
        per_arm[arm] = {
            "years": int(len(frame)),
            "cagr": cagr(frame.net_return),
            "cdi_cagr": cagr(frame.cdi_net_return),
            "years_beating_cdi": int((frame.net_return > frame.cdi_net_return).sum()),
            "average_equity_weight": float(frame.equity_weight.mean()),
            "worst_year": float(frame.net_return.min()),
        }
    contamination = None
    if {"named", "anonymised"} <= set(per_arm):
        paired = results[results.arm.isin(["named", "anonymised"])].pivot(
            index="decision_year", columns="arm", values="net_return").dropna()
        if not paired.empty:
            from scipy import stats
            difference = paired["named"] - paired["anonymised"]
            statistic, p_value = stats.ttest_1samp(difference, 0.0)
            contamination = {
                "paired_years": int(len(paired)),
                "named_cagr": cagr(paired["named"]),
                "anonymised_cagr": cagr(paired["anonymised"]),
                "contamination_annualised": cagr(paired["named"]) - cagr(paired["anonymised"]),
                "mean_annual_difference": float(difference.mean()),
                "p_value": float(p_value),
                "years_named_won": int((difference > 0).sum()),
                "reading": ("A positive, significant gap means the named arm profited from recognising companies "
                            "rather than from reading their figures. The anonymised arm is then the only defensible "
                            "number for this period."),
            }
    summary = {
        "model": args.model,
        "arms": per_arm,
        "contamination": contamination,
        "decoupling_note": ("In the named and anonymised arms the model never sets a weight: its bounded score tilts "
                            "expected return inside the convex optimiser, which still enforces every cap. The "
                            "monolithic arm is the counterfactual where the model is trusted with weights; see "
                            "constraint_audit.csv."),
        "cache_directory": str(cache).replace("\\", "/"),
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
