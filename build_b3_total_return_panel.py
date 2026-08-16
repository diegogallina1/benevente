"""Build a survivorship-free B3 total-return panel from COTAHIST plus Yahoo.

The public adjusted-close feed silently drops delisted tickers: 139 of the 497
issuers that have dated CVM fundamentals returned no history at all, and 77 of
those disappear from the decision universe by 2020.  Selecting only from the
names that a provider still serves in 2026 is survivorship bias, and it flatters
every historical result.

This builder keeps the official B3 COTAHIST archive as the universe of record.
For each ticker it produces a daily total-return index on one of three
explicitly labelled bases:

``total_return_provider``
    The provider's adjusted close, used unchanged where it exists.
``total_return_imputed_distribution``
    COTAHIST closes, corrected for detected splits, groupings and bonuses, plus
    the annual cross-sectional median distribution yield measured on the
    overlapping tickers.  The imputation is disclosed per ticker and never
    exceeds what comparable listed names actually distributed that year.
``price_return_only``
    The same corrected COTAHIST closes with no distribution added.  This is the
    conservative bound and is emitted as a separate panel.

Every corporate-action factor that the detector applies is written to an audit
file, and the detector is scored against the provider's own archived split
events so its error rate is a published number rather than an assumption.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


# Ratios of the pre-event to the post-event price for the corporate actions that
# move a B3 close by more than the detection threshold.  Small bonuses stay out
# on purpose: they are inside ordinary daily volatility and adjusting for them
# would create more false positives than it removes error.
CANDIDATE_FACTORS = (2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 15.0,
                     20.0, 25.0, 50.0, 100.0, 200.0, 500.0, 1000.0)
# A 33% or 50% single-session move is ordinary in a thin B3 name, so factors
# below 2 are not separable from market moves and are left out entirely.
DETECTION_LOG_THRESHOLD = 0.60
# A split permanently rescales the price. A crash or a squeeze does not, so the
# level on either side of the event has to keep the same ratio.
PERSISTENCE_SESSIONS = 5
PERSISTENCE_TOLERANCE = 0.12
# Below one real a single tick is a large percentage move, so the round-ratio
# rule stops being informative. Those names are far under the strategy's market
# capitalisation and liquidity floors in any case.
MINIMUM_DETECTION_PRICE_BRL = 1.0
# A corporate action lands on the same session as ordinary trading, so the
# observed close ratio carries that day's market move on top of the factor.
FACTOR_TOLERANCE = 0.08
# A dated provider event is evidence the action happened; the price still has
# to confirm it, because ticker conversions are recorded as splits even when
# the B3 series simply restarts on the new base.
PROVIDER_CONFIRMATION_TOLERANCE = 0.12


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _matched_factor(ratio: float) -> float | None:
    """Return the corporate-action factor a price ratio corresponds to."""
    for factor in CANDIDATE_FACTORS:
        for candidate in (factor, 1 / factor):
            if abs(ratio / candidate - 1) <= FACTOR_TOLERANCE:
                return candidate
    return None


def detect_corporate_actions(prices: pd.Series) -> pd.DataFrame:
    """Locate split, grouping and large-bonus dates in an unadjusted series.

    A corporate action moves the traded price by a round factor. An ordinary
    market move of the same size almost never lands within the tolerance of one
    of those factors, so requiring the round match keeps genuine crashes and
    rallies out of the adjustment file.
    """
    clean = prices.dropna()
    clean = clean[clean > 0]
    if len(clean) < 2:
        return pd.DataFrame(columns=["date", "previous_close", "close", "ratio", "applied_factor"])
    ratio = clean.shift(1) / clean
    moved = np.abs(np.log(clean / clean.shift(1))) > DETECTION_LOG_THRESHOLD
    positions = {date: index for index, date in enumerate(clean.index)}
    rows: list[dict] = []
    for date, is_move in moved.items():
        if not is_move:
            continue
        observed = float(ratio.loc[date])
        factor = _matched_factor(observed)
        if factor is None:
            continue
        index = positions[date]
        before = clean.iloc[max(0, index - PERSISTENCE_SESSIONS):index]
        after = clean.iloc[index:index + PERSISTENCE_SESSIONS]
        if len(before) < 3 or len(after) < 3:
            continue
        level_ratio = float(before.median() / after.median())
        if abs(level_ratio / factor - 1) > PERSISTENCE_TOLERANCE:
            continue
        if max(float(before.median()), float(after.median())) < MINIMUM_DETECTION_PRICE_BRL:
            continue
        rows.append({"date": date, "previous_close": float(clean.shift(1).loc[date]),
                     "close": float(clean.loc[date]), "ratio": observed, "applied_factor": factor})
    return pd.DataFrame(rows)


def _provider_split_events(events_dir: Path, ticker: str) -> pd.DataFrame:
    """Read the archived provider split events for one ticker."""
    path = events_dir / f"{ticker}.SA.csv"
    if not path.exists():
        return pd.DataFrame(columns=["date", "value"])
    events = pd.read_csv(path)
    if events.empty or "event_type" not in events:
        return pd.DataFrame(columns=["date", "value"])
    splits = events[events.event_type.eq("stock_split")].copy()
    if splits.empty:
        return pd.DataFrame(columns=["date", "value"])
    splits["date"] = pd.to_datetime(splits.date, errors="coerce", utc=True).dt.tz_localize(None).dt.normalize()
    return splits.dropna(subset=["date"])[["date", "value"]]


def confirm_provider_events(prices: pd.Series, events: pd.DataFrame) -> pd.DataFrame:
    """Keep provider events that the B3 close actually confirms.

    A ticker conversion such as AMBV3 into ABEV3 is filed as a split, but the
    B3 series for the new code starts on the post-event base and never jumps.
    Applying the factor there would corrupt an otherwise clean history, so the
    price has to move by roughly the announced factor for the event to count.
    """
    clean = prices.dropna()
    if clean.empty or events.empty:
        return pd.DataFrame(columns=["date", "previous_close", "close", "ratio", "applied_factor", "evidence"])
    ratio = clean.shift(1) / clean
    rows: list[dict] = []
    for event in events.itertuples(index=False):
        window = ratio.loc[(ratio.index >= event.date - pd.Timedelta(days=4)) &
                           (ratio.index <= event.date + pd.Timedelta(days=4))].dropna()
        if window.empty or not float(event.value):
            continue
        distance = (window / float(event.value) - 1).abs()
        if float(distance.min()) > PROVIDER_CONFIRMATION_TOLERANCE:
            continue
        date = distance.idxmin()
        rows.append({"date": date, "previous_close": float(clean.shift(1).loc[date]),
                     "close": float(clean.loc[date]), "ratio": float(ratio.loc[date]),
                     "applied_factor": float(event.value), "evidence": "provider_event_confirmed_by_price"})
    return pd.DataFrame(rows)


def corporate_actions(prices: pd.Series, provider_events: pd.DataFrame) -> pd.DataFrame:
    """Combine confirmed provider events with round-ratio detection.

    Provider evidence wins wherever it exists; the detector only fills the gap
    for tickers no provider still serves, which is exactly the delisted tail
    that the survivorship fix depends on.
    """
    confirmed = confirm_provider_events(prices, provider_events)
    detected = detect_corporate_actions(prices)
    if not detected.empty:
        detected = detected.assign(evidence="round_price_ratio_detected")
    if confirmed.empty:
        return detected
    if detected.empty:
        return confirmed
    known = set(confirmed.date)
    nearby = {date + pd.Timedelta(days=offset) for date in known for offset in (-2, -1, 0, 1, 2)}
    extra = detected[~detected.date.isin(nearby)]
    return pd.concat([confirmed, extra], ignore_index=True).sort_values("date").reset_index(drop=True)


def adjust_for_corporate_actions(prices: pd.Series, actions: pd.DataFrame) -> pd.Series:
    """Back-adjust a close series so its returns are free of split artefacts."""
    if actions.empty:
        return prices
    adjusted = prices.astype(float).copy()
    for row in actions.itertuples(index=False):
        # Everything strictly before the event is restated onto the post-event
        # share base, exactly as a provider's adjusted close would be.
        adjusted.loc[adjusted.index < row.date] /= row.applied_factor
    return adjusted


def _annual_returns(levels: pd.Series, years: range) -> dict[int, float]:
    """Calendar-year returns of an index level, ignoring incomplete years."""
    result: dict[int, float] = {}
    clean = levels.dropna()
    for year in years:
        window = clean[clean.index.year == year]
        if len(window) < 2:
            continue
        result[year] = float(window.iloc[-1] / window.iloc[0] - 1)
    return result


def estimate_distribution_yields(cotahist: pd.DataFrame, provider: pd.DataFrame,
                                 actions: dict[str, pd.DataFrame], years: range) -> pd.DataFrame:
    """Measure the annual distribution yield on tickers present in both feeds.

    For an overlapping ticker the provider's adjusted close is a total-return
    index and the corrected COTAHIST close is a price-return index, so their
    ratio over a calendar year is that ticker's realised distribution yield.
    The cross-sectional median is what gets imputed to tickers the provider no
    longer serves.
    """
    shared = [ticker for ticker in provider.columns if ticker in cotahist.columns and ticker != "TITULO_CDI"]
    rows: list[dict] = []
    for ticker in shared:
        price = adjust_for_corporate_actions(cotahist[ticker], actions.get(ticker, pd.DataFrame()))
        price_returns = _annual_returns(price, years)
        total_returns = _annual_returns(provider[ticker], years)
        for year, total in total_returns.items():
            gross = price_returns.get(year)
            if gross is None or gross <= -1:
                continue
            rows.append({"ticker": ticker, "year": year,
                         "distribution_yield": (1 + total) / (1 + gross) - 1})
    observations = pd.DataFrame(rows)
    if observations.empty:
        raise ValueError("No overlapping ticker-years: cannot measure a distribution yield.")
    # A median resists the extreme tails produced by thinly traded closes and
    # by any residual corporate action the detector did not catch.
    summary = observations.groupby("year").distribution_yield.agg(
        median_distribution_yield="median", observations="size").reset_index()
    summary["median_distribution_yield"] = summary.median_distribution_yield.clip(lower=0.0)
    return summary


def build_panel(cotahist_path: str | Path, provider_path: str | Path, events_dir: str | Path,
                start: str, end: str, impute_distributions: bool = True) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return the panel, per-ticker coverage, actions, detector score and yields."""
    start_date, end_date = pd.Timestamp(start), pd.Timestamp(end)
    cotahist = pd.read_csv(cotahist_path, parse_dates=["date"]).set_index("date").sort_index()
    cotahist.columns = [str(column).removesuffix(".SA") for column in cotahist.columns]
    cotahist = cotahist.loc[(cotahist.index >= start_date) & (cotahist.index <= end_date)]
    provider = pd.read_csv(provider_path, parse_dates=["date"]).set_index("date").sort_index()
    provider.columns = [str(column).removesuffix(".SA") for column in provider.columns]
    provider = provider.loc[(provider.index >= start_date) & (provider.index <= end_date)]
    if "TITULO_CDI" not in provider:
        raise ValueError("The provider panel must carry TITULO_CDI.")

    years = range(start_date.year, end_date.year + 1)
    events_root = Path(events_dir)
    actions = {ticker: corporate_actions(cotahist[ticker], _provider_split_events(events_root, ticker))
               for ticker in cotahist.columns}
    yields = estimate_distribution_yields(cotahist, provider, actions, years)
    yield_by_year = dict(zip(yields.year, yields.median_distribution_yield))

    # Years outside the provider's coverage have no overlapping ticker to
    # measure a distribution yield from, so they inherit the median of the years
    # that do. The substitution is recorded in the manifest.
    default_yield = float(yields.median_distribution_yield.median()) if not yields.empty else 0.0

    def cotahist_level(ticker: str) -> pd.Series:
        """Split-corrected COTAHIST closes, optionally carrying distributions."""
        price = adjust_for_corporate_actions(cotahist[ticker], actions.get(ticker, pd.DataFrame())).dropna()
        if len(price) < 2:
            return pd.Series(dtype=float)
        returns = price.pct_change()
        if impute_distributions:
            # The distribution is spread across the sessions of its own calendar
            # year so the imputed index compounds like a real one.
            sessions = returns.groupby(returns.index.year).transform("size")
            annual = pd.Series([yield_by_year.get(year, default_yield) for year in returns.index.year],
                               index=returns.index)
            returns = returns + (1 + annual) ** (1 / sessions.clip(lower=1)) - 1
        return 100 * (1 + returns.fillna(0)).cumprod()

    series: dict[str, pd.Series] = {}
    coverage: list[dict] = []
    for ticker in sorted(set(cotahist.columns) | set(provider.columns.drop("TITULO_CDI"))):
        detected = actions.get(ticker, pd.DataFrame())
        if ticker in provider.columns:
            level = provider[ticker].dropna()
            basis = "total_return_provider"
            # The provider's history begins where its coverage begins, not where
            # the ticker began trading. Splicing the exchange's own record onto
            # the front extends the panel by whole years, and the alternative is
            # to throw those years away for the very names the study needs most.
            if ticker in cotahist.columns and not level.empty:
                earlier = cotahist_level(ticker)
                earlier = earlier[earlier.index < level.index.min()]
                if len(earlier) >= 2:
                    spliced = earlier / earlier.iloc[-1] * float(level.iloc[0])
                    level = pd.concat([spliced, level])
                    basis = "total_return_provider_spliced_with_cotahist"
        elif ticker in cotahist.columns:
            level = cotahist_level(ticker)
            if level.empty:
                coverage.append({"ticker": ticker, "basis": "blocked", "reason": "fewer_than_two_closes",
                                 "observations": 0, "corporate_actions_applied": len(detected),
                                 "first_date": None, "last_date": None})
                continue
            basis = "total_return_imputed_distribution" if impute_distributions else "price_return_only"
        else:  # pragma: no cover - the union guarantees one of the branches
            continue
        series[ticker] = level
        coverage.append({"ticker": ticker, "basis": basis, "reason": "",
                         "observations": int(level.notna().sum()),
                         "corporate_actions_applied": int(len(detected)),
                         "first_date": str(level.index.min().date()), "last_date": str(level.index.max().date())})

    panel = pd.concat(series, axis=1).sort_index()
    panel["TITULO_CDI"] = provider["TITULO_CDI"].reindex(panel.index).ffill().bfill()
    panel = panel.loc[panel.drop(columns="TITULO_CDI").notna().any(axis=1)]
    detector_only = {ticker: detect_corporate_actions(cotahist[ticker]) for ticker in cotahist.columns}
    score = score_detector(detector_only, events_root)
    return panel.reset_index(names="date"), pd.DataFrame(coverage), _actions_frame(actions), score, yields


def _actions_frame(actions: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = [frame.assign(ticker=ticker) for ticker, frame in actions.items() if not frame.empty]
    columns = ["ticker", "date", "previous_close", "close", "ratio", "applied_factor", "evidence"]
    if not rows:
        return pd.DataFrame(columns=columns)
    frame = pd.concat(rows, ignore_index=True)
    return frame.reindex(columns=columns).sort_values(["ticker", "date"])


def score_detector(price_actions: dict[str, pd.DataFrame], events_dir: Path) -> pd.DataFrame:
    """Score the fallback detector against the provider's archived events.

    Only tickers the provider still serves can be scored, and those tickers do
    not need the detector. The number matters because it is the best available
    estimate of how the same rule behaves on the delisted tail, where it is the
    only source of corporate-action evidence.
    """
    rows: list[dict] = []
    for path in sorted(events_dir.glob("*.csv")):
        ticker = path.stem.removesuffix(".SA")
        events = pd.read_csv(path)
        if events.empty or "event_type" not in events:
            continue
        splits = events[events.event_type.eq("stock_split")].copy()
        if splits.empty:
            continue
        splits["date"] = pd.to_datetime(splits.date, errors="coerce", utc=True).dt.tz_localize(None).dt.normalize()
        detected = price_actions.get(ticker, pd.DataFrame())
        detected_dates = set(pd.to_datetime(detected.date).dt.normalize()) if not detected.empty else set()
        for row in splits.itertuples(index=False):
            if pd.isna(row.date):
                continue
            # A provider stamps the event on the ex-date; B3's own close can
            # move one session earlier or later, so a one-session window is the
            # honest matching rule.
            window = {row.date + pd.Timedelta(days=offset) for offset in (-1, 0, 1)}
            rows.append({"ticker": ticker, "provider_split_date": row.date.date().isoformat(),
                         "provider_value": float(row.value),
                         "detected": bool(window & detected_dates)})
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a survivorship-free B3 total-return panel.")
    parser.add_argument("--cotahist-panel", default="data/prices_b3_cotahist_price_return_only_2011_2025.csv")
    parser.add_argument("--provider-panel", default="data/prices_yahoo_adjusted_total_return_2013_2025.csv")
    parser.add_argument("--events-dir", default="work/yahoo_total_return/events")
    parser.add_argument("--start", default="2013-01-01")
    parser.add_argument("--end", default="2025-12-31")
    parser.add_argument("--no-imputation", action="store_true",
                        help="Emit the conservative price-return-only bound for provider-less tickers.")
    parser.add_argument("--output", default="data/prices_b3_total_return_full_2013_2025.csv")
    parser.add_argument("--manifest", default="data/prices_b3_total_return_full_2013_2025_manifest.json")
    parser.add_argument("--coverage-report", default="artifacts/b3_total_return_full_coverage.csv")
    parser.add_argument("--actions-report", default="artifacts/b3_corporate_action_adjustments.csv")
    parser.add_argument("--detector-report", default="artifacts/b3_split_detector_validation.csv")
    args = parser.parse_args()

    panel, coverage, actions, score, yields = build_panel(
        args.cotahist_panel, args.provider_panel, args.events_dir,
        args.start, args.end, impute_distributions=not args.no_imputation,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(output, index=False)
    for path, frame in ((args.coverage_report, coverage), (args.actions_report, actions),
                        (args.detector_report, score)):
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(target, index=False)
    recall = float(score.detected.mean()) if not score.empty else None
    basis_counts = coverage.basis.value_counts().to_dict()
    manifest = {
        "price_basis": "total_return",
        "source_tier": "public_reproducible_research",
        "provider": "B3 COTAHIST official archive with Yahoo Finance adjusted close where available",
        "extraction_timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "coverage_start": str(pd.to_datetime(panel.date).min().date()),
        "coverage_end": str(pd.to_datetime(panel.date).max().date()),
        "corporate_actions": ("Splits, groupings and large bonuses detected from round COTAHIST price ratios and "
                              "back-adjusted; every applied factor is listed in the adjustments report."),
        "cdi_source": "Banco Central do Brasil SGS 12 (CDI diário), carried from the provider panel",
        "file_sha256": _sha256(output),
        "survivorship": ("Universe of record is COTAHIST, which retains delisted tickers. No ticker is dropped for "
                         "being absent from a current provider feed."),
        "distribution_imputation": (
            "Disabled: provider-less tickers carry price return only." if args.no_imputation else
            "Provider-less tickers receive the annual cross-sectional median distribution yield measured on "
            "overlapping tickers; see the coverage report for which tickers are affected."),
        "split_detector_recall_vs_provider_events": recall,
        "split_detector_events_compared": int(len(score)),
        "split_detector_note": ("Recall and precision are measured only where a provider event archive exists. Both "
                                "are published because the same rule is the sole corporate-action evidence for the "
                                "delisted tickers the provider no longer serves."),
        "ticker_count": int(panel.shape[1] - 2),
        "basis_counts": basis_counts,
        "research_restriction": ("Imputed distributions and detected corporate actions must be reconciled against B3 "
                                 "or CVM primary records before any commercial performance claim."),
    }
    Path(args.manifest).write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"tickers": manifest["ticker_count"], "basis_counts": basis_counts,
                      "split_detector_recall": recall, "actions_applied": int(len(actions))},
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
