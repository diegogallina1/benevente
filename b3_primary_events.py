"""Archive primary B3 corporate-event records in the reconciliation schema.

The B3 listed-company service exposes two complementary records: a paginated
cash-distribution history and a company supplement containing share events and
subscription rights.  This downloader stores the exact event date supplied by
B3 (last cum-rights date) and translates it to the next observed trading
session for each ticker.  It never guesses an event when a company, security
class or trading session cannot be matched.

The resulting archive is evidence for reconciliation.  It does not, by itself,
turn an already adjusted provider series into an institutionally verified
total-return panel.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import argparse
import base64
import hashlib
import json
import re
import time
import unicodedata

import pandas as pd

from corporate_action_reconciliation import file_sha256


B3_API = "https://sistemaswebb3-listados.b3.com.br/listedCompaniesProxy/CompanyCall"
OFFICIAL_PAGE = "https://sistemaswebb3-listados.b3.com.br/dividensOtherCorpActPage/"
CASH_PAGE_SIZE = 120


def _compact_json(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _endpoint(method: str, payload: dict) -> str:
    encoded = base64.b64encode(_compact_json(payload).encode("utf-8")).decode("ascii")
    return f"{B3_API}/{method}/{encoded}"


def _get_json(method: str, payload: dict, retries: int = 4) -> tuple[object, str]:
    url = _endpoint(method, payload)
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = Request(url, headers={"User-Agent": "Benevente-Research/1.0"})
            with urlopen(request, timeout=45) as response:
                raw = response.read().decode("utf-8-sig")
            return json.loads(raw), url
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = error
            time.sleep(0.5 * (2 ** attempt))
    raise RuntimeError(f"B3 request failed after {retries} attempts: {method}") from last_error


def _number(value: object) -> float | None:
    text = str(value or "").strip().replace(".", "").replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _date(value: object) -> pd.Timestamp | None:
    parsed = pd.to_datetime(value, format="%d/%m/%Y", errors="coerce")
    return None if pd.isna(parsed) else pd.Timestamp(parsed)


def _plain(value: object) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "").strip().upper())
    return "".join(character for character in normalized if not unicodedata.combining(character))


def _issuer(ticker: str) -> str:
    match = re.match(r"^([A-Z0-9]{4})", ticker.upper().removesuffix(".SA"))
    return match.group(1) if match else ""


def _security_class(ticker: str) -> str:
    symbol = ticker.upper().removesuffix(".SA")
    if symbol.endswith("11"):
        return "UNT"
    suffix = re.search(r"(\d+)[A-Z]?$", symbol)
    number = suffix.group(1) if suffix else ""
    return {"3": "ON", "4": "PN", "5": "PNA", "6": "PNB", "7": "PNC", "8": "PND"}.get(number, "")


def _cash_type(label: object) -> str:
    name = _plain(label)
    mapping = {
        "DIVIDENDO": "dividend",
        "JRS CAP PROPRIO": "jcp",
        "JUROS CAP PROPRIO": "jcp",
        "RESTITUICAO CAPITAL": "capital_restitution",
        "REST CAP DIN": "capital_restitution",
        "AMORTIZACAO": "amortization",
        "RENDIMENTO": "income",
        "INCORPORACAO": "merger",
        "CIS RED CAP": "spin_off",
        "CIS RED CAP QTD": "spin_off",
        "REST CAP ACOES": "spin_off",
    }
    return mapping.get(name, "unknown")


def _share_type(label: object) -> str:
    name = _plain(label)
    return {
        "DESDOBRAMENTO": "split", "GRUPAMENTO": "reverse_split", "BONIFICACAO": "bonus",
        "INCORPORACAO": "merger", "CIS RED CAP": "spin_off", "CIS RED CAP QTD": "spin_off",
        "REST CAP ACOES": "spin_off",
    }.get(name, "unknown")


def _share_factor(label: object, value: object) -> float | None:
    factor = _number(value)
    if factor is None or factor <= 0:
        return None
    return factor if _plain(label) == "GRUPAMENTO" else 1.0 + factor / 100.0


def _event_id(parts: list[object]) -> str:
    canonical = "|".join(str(part or "").strip() for part in parts)
    return "b3-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


def _published_at(value: object, extracted_at: str) -> str:
    date = _date(value)
    return date.tz_localize("UTC").isoformat() if date is not None else extracted_at


@dataclass(frozen=True)
class TickerContext:
    ticker: str
    isin: str
    issuer: str
    security_class: str
    trading_dates: tuple[pd.Timestamp, ...]

    @property
    def coverage_start(self) -> str:
        return self.trading_dates[0].date().isoformat()

    @property
    def coverage_end(self) -> str:
        return self.trading_dates[-1].date().isoformat()

    def next_session(self, last_cum_date: object) -> str | None:
        cum = _date(last_cum_date)
        if cum is None:
            return None
        # The current B3 endpoint can return events from long before this
        # ticker's observed price history.  Do not map an old right to the
        # first session of the panel and thereby manufacture an adjustment.
        if cum < self.trading_dates[0] - pd.Timedelta(days=7):
            return None
        for session in self.trading_dates:
            if session > cum:
                return session.date().isoformat()
        return None


def load_contexts(prices_path: str | Path, mapping_path: str | Path) -> list[TickerContext]:
    prices = pd.read_csv(prices_path)
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce")
    mapping = pd.read_csv(mapping_path, dtype=str)
    mapping["ticker"] = mapping["ticker"].astype(str).str.upper().str.removesuffix(".SA")
    mapping = mapping.dropna(subset=["isin"]).drop_duplicates(["ticker", "isin"], keep="last")
    isin_by_ticker = mapping.groupby("ticker")["isin"].last().to_dict()
    contexts = []
    for column in prices.columns:
        ticker = str(column).upper().removesuffix(".SA")
        if ticker in {"DATE", "TITULO_CDI"}:
            continue
        dates = tuple(prices.loc[pd.to_numeric(prices[column], errors="coerce").notna(), "date"].dropna().sort_values())
        if not dates:
            continue
        contexts.append(TickerContext(
            ticker=ticker,
            isin=str(isin_by_ticker.get(ticker, "")).strip().upper(),
            issuer=_issuer(ticker),
            security_class=_security_class(ticker),
            trading_dates=dates,
        ))
    return contexts


def fetch_cash_history(trading_name: str) -> tuple[list[dict], list[str]]:
    rows: list[dict] = []
    urls: list[str] = []
    page = 1
    total: int | None = None
    while total is None or len(rows) < total:
        payload = {"language": "pt-br", "pageNumber": page, "pageSize": CASH_PAGE_SIZE,
                   "tradingName": re.sub(r"[^A-Z0-9 ]+", "", _plain(trading_name))}
        response, url = _get_json("GetListedCashDividends", payload)
        urls.append(url)
        if not isinstance(response, dict):
            raise RuntimeError(f"Unexpected cash-history response for {trading_name}")
        batch = response.get("results") or []
        for item in batch:
            item["_b3_row_number"] = len(rows) + 1
            item["_source_url"] = url
        total = int(response.get("page", {}).get("totalRecords") or len(batch))
        rows.extend(batch)
        if not batch or len(batch) < CASH_PAGE_SIZE:
            break
        page += 1
    return rows, urls


def normalize_issuer_events(
    contexts: list[TickerContext], supplement: dict, cash_rows: list[dict],
    supplement_url: str, cash_urls: list[str], extracted_at: str,
) -> tuple[list[dict], list[dict]]:
    events: list[dict] = []
    coverage: list[dict] = []
    isin_map: dict[str, list[TickerContext]] = {}
    class_map: dict[str, list[TickerContext]] = {}
    for context in contexts:
        if context.isin:
            isin_map.setdefault(context.isin, []).append(context)
        if context.security_class:
            class_map.setdefault(context.security_class, []).append(context)

    for raw in cash_rows:
        candidates = class_map.get(_plain(raw.get("typeStock")), [])
        for context in candidates:
            ex_date = context.next_session(raw.get("lastDatePriorEx"))
            if not ex_date:
                continue
            event_type = _cash_type(raw.get("corporateAction"))
            cash = _number(raw.get("valueCash"))
            # The paginated B3 response may contain economically distinct
            # installments with otherwise identical fields.  Its stable row
            # position is therefore part of the identifier; collapsing those
            # rows would understate the cash received.
            parts = [context.ticker, event_type, ex_date, cash, raw.get("dateApproval"),
                     raw.get("lastDatePriorEx"), raw.get("valueCash"), raw.get("corporateAction"),
                     raw.get("_b3_row_number")]
            events.append({
                "event_id": _event_id(parts), "ticker": context.ticker, "event_type": event_type,
                "ex_date": ex_date, "cash_per_old_share": cash, "share_factor": None,
                "source_url": raw.get("_source_url") or (cash_urls[0] if cash_urls else OFFICIAL_PAGE),
                "published_at": _published_at(raw.get("dateApproval"), extracted_at),
                "status": "confirmed" if event_type != "unknown" else "cancelled",
                "resolution": "", "b3_last_cum_date": raw.get("lastDatePriorEx", ""),
                "b3_payment_date": "", "b3_label": raw.get("corporateAction", ""),
                "b3_security_class": raw.get("typeStock", ""),
            })

    for raw in supplement.get("stockDividends") or []:
        for context in isin_map.get(str(raw.get("isinCode") or raw.get("assetIssued") or "").strip().upper(), []):
            ex_date = context.next_session(raw.get("lastDatePrior"))
            if not ex_date:
                continue
            event_type = _share_type(raw.get("label"))
            factor = _share_factor(raw.get("label"), raw.get("factor"))
            parts = [context.ticker, event_type, ex_date, factor, raw.get("approvedOn"), raw.get("isinCode")]
            events.append({
                "event_id": _event_id(parts), "ticker": context.ticker, "event_type": event_type,
                "ex_date": ex_date, "cash_per_old_share": None, "share_factor": factor,
                "source_url": supplement_url, "published_at": _published_at(raw.get("approvedOn"), extracted_at),
                "status": "confirmed" if event_type != "unknown" else "cancelled", "resolution": "",
                "b3_last_cum_date": raw.get("lastDatePrior", ""), "b3_payment_date": "",
                "b3_label": raw.get("label", ""), "b3_security_class": context.security_class,
            })

    for raw in supplement.get("subscriptions") or []:
        for context in isin_map.get(str(raw.get("isinCode") or raw.get("assetIssued") or "").strip().upper(), []):
            ex_date = context.next_session(raw.get("lastDatePrior"))
            if not ex_date:
                continue
            parts = [context.ticker, "subscription", ex_date, raw.get("percentage"), raw.get("priceUnit"),
                     raw.get("approvedOn"), raw.get("isinCode")]
            events.append({
                "event_id": _event_id(parts), "ticker": context.ticker, "event_type": "subscription",
                "ex_date": ex_date, "cash_per_old_share": None, "share_factor": None,
                "source_url": supplement_url, "published_at": _published_at(raw.get("approvedOn"), extracted_at),
                "status": "confirmed", "resolution": "", "b3_last_cum_date": raw.get("lastDatePrior", ""),
                "b3_payment_date": raw.get("subscriptionDate", ""), "b3_label": raw.get("label", ""),
                "b3_security_class": context.security_class,
            })

    for context in contexts:
        coverage.append({
            "ticker": context.ticker, "coverage_start": context.coverage_start,
            "coverage_end": context.coverage_end,
            "status": "queried_current_endpoint" if context.isin else "partial",
            "source_url": supplement_url, "extracted_at": extracted_at,
            "note": (
                "B3 current company supplement and paginated cash history queried; "
                "historical completeness not certified"
            ) if context.isin
                    else "ticker has no ISIN mapping; events cannot be assigned safely",
        })
    return events, coverage


def archive_primary_events(
    prices_path: str | Path, mapping_path: str | Path, events_path: str | Path,
    coverage_path: str | Path, manifest_path: str | Path, issuer_limit: int | None = None,
    resume: bool = False,
) -> dict:
    contexts = load_contexts(prices_path, mapping_path)
    events_target, coverage_target, manifest_target = map(Path, (events_path, coverage_path, manifest_path))
    prior_events = pd.DataFrame()
    prior_coverage = pd.DataFrame()
    completed_tickers: set[str] = set()
    if resume and events_target.exists() and coverage_target.exists():
        prior_events = pd.read_csv(events_target)
        prior_coverage = pd.read_csv(coverage_target)
        if not prior_events.empty and "b3_last_cum_date" in prior_events:
            cum_date = pd.to_datetime(
                prior_events["b3_last_cum_date"], format="%d/%m/%Y", errors="coerce"
            )
            ex_date = pd.to_datetime(prior_events["ex_date"], errors="coerce")
            stale_bridge = cum_date.notna() & ex_date.notna() & (
                ex_date - cum_date > pd.Timedelta(days=7)
            )
            prior_events = prior_events.loc[~stale_bridge].copy()
        if not prior_events.empty and "b3_label" in prior_events:
            remapped = prior_events["b3_label"].map(_cash_type)
            changed = prior_events["event_type"].eq("unknown") & remapped.ne("unknown")
            prior_events.loc[changed, "event_type"] = remapped.loc[changed]
            prior_events.loc[changed, "status"] = "confirmed"
        archival_status = prior_coverage.status.astype(str).str.lower()
        completed_tickers = set(
            prior_coverage.loc[
                archival_status.isin({"complete", "queried_current_endpoint"}), "ticker"
            ]
            .astype(str).str.upper().str.removesuffix(".SA")
        )
        prior_coverage.loc[
            archival_status.eq("complete"), "status"
        ] = "queried_current_endpoint"
    grouped: dict[str, list[TickerContext]] = {}
    for context in contexts:
        if context.issuer and context.ticker not in completed_tickers:
            grouped.setdefault(context.issuer, []).append(context)
    issuers = sorted(grouped)
    if issuer_limit:
        issuers = issuers[:issuer_limit]
    extracted_at = datetime.now(timezone.utc).isoformat()
    all_events: list[dict] = prior_events.to_dict("records") if not prior_events.empty else []
    all_coverage: list[dict] = (
        prior_coverage[prior_coverage.ticker.astype(str).str.upper().str.removesuffix(".SA").isin(completed_tickers)]
        .to_dict("records") if not prior_coverage.empty else []
    )
    failures: list[dict] = []
    for position, issuer in enumerate(issuers, start=1):
        try:
            supplement, supplement_url = _get_json(
                "GetListedSupplementCompany", {"issuingCompany": issuer, "language": "pt-br"}
            )
            if isinstance(supplement, list) and len(supplement) == 1:
                supplement = supplement[0]
            if not isinstance(supplement, dict) or not supplement.get("code"):
                raise RuntimeError("company not found in the current B3 listed-company service")
            cash, cash_urls = fetch_cash_history(str(supplement.get("tradingName") or issuer))
            events, coverage = normalize_issuer_events(
                grouped[issuer], supplement, cash, supplement_url, cash_urls, extracted_at
            )
            all_events.extend(events)
            all_coverage.extend(coverage)
        except Exception as error:  # a failed issuer must remain visible in the ledger
            failures.append({"issuer": issuer, "error": str(error)})
            for context in grouped[issuer]:
                all_coverage.append({
                    "ticker": context.ticker, "coverage_start": context.coverage_start,
                    "coverage_end": context.coverage_end, "status": "failed",
                    "source_url": OFFICIAL_PAGE, "extracted_at": extracted_at,
                    "note": str(error),
                })
        if position % 25 == 0 or position == len(issuers):
            print(f"B3 primary events: {position}/{len(issuers)} issuers", flush=True)

    event_columns = [
        "event_id", "ticker", "event_type", "ex_date", "cash_per_old_share", "share_factor",
        "source_url", "published_at", "status", "resolution", "b3_last_cum_date",
        "b3_payment_date", "b3_label", "b3_security_class",
    ]
    events = pd.DataFrame(all_events, columns=event_columns)
    if not events.empty:
        events = events.drop_duplicates("event_id").sort_values(["ticker", "ex_date", "event_id"])
    coverage = pd.DataFrame(all_coverage).sort_values("ticker")
    for target in (events_target, coverage_target, manifest_target):
        target.parent.mkdir(parents=True, exist_ok=True)
    events.to_csv(events_target, index=False)
    coverage.to_csv(coverage_target, index=False)
    manifest = {
        "source": "B3 listed-company primary records",
        "official_page": OFFICIAL_PAGE,
        "extracted_at": extracted_at,
        "price_panel": str(prices_path).replace("\\", "/"),
        "mapping": str(mapping_path).replace("\\", "/"),
        "issuer_count_requested": len({_issuer(context.ticker) for context in contexts if _issuer(context.ticker)}),
        "issuer_count_queried_this_run": len(issuers),
        "ticker_count_requested": len(contexts),
        "ticker_count_endpoint_queried": int(
            coverage.status.eq("queried_current_endpoint").sum()
        ),
        "ticker_count_historically_reconciled": 0,
        "event_count": int(len(events)),
        "cash_event_count": int(events.event_type.isin(["dividend", "jcp", "income", "amortization", "capital_restitution"]).sum()) if not events.empty else 0,
        "share_event_count": int(events.event_type.isin(["split", "reverse_split", "bonus"]).sum()) if not events.empty else 0,
        "unresolved_subscription_count": int(events.event_type.eq("subscription").sum()) if not events.empty else 0,
        "unresolved_manual_event_count": int(events.event_type.isin(["subscription", "merger", "spin_off", "ticker_change", "delisting"]).sum()) if not events.empty else 0,
        "failed_issuers": failures,
        "events_sha256": file_sha256(events_target),
        "coverage_sha256": file_sha256(coverage_target),
        "status": "primary_endpoint_archive_partial",
        "archive_validation": {
            "official_source": True,
            "endpoint_query_rate": float(
                coverage.status.eq("queried_current_endpoint").mean()
            ) if len(coverage) else 0.0,
            "historical_reconciliation_rate": 0.0,
            "duplicate_event_ids": int(events.event_id.duplicated().sum()) if not events.empty else 0,
            "invalid_normalized_records": int(events.event_type.eq("unknown").sum()) if not events.empty else 0,
            "unresolved_manual_events": int(events.event_type.isin(["subscription", "merger", "spin_off", "ticker_change", "delisting"]).sum()) if not events.empty else 0,
            "status": "blocked_current_endpoint_is_not_a_complete_historical_ledger",
        },
        "verification_note": (
            "A successful response from the current B3 page is evidence that the endpoint was queried, "
            "not that every historical event was returned. This archive does not certify the existing "
            "adjusted price panel. Institutional verification requires a complete historical primary or "
            "licensed ledger, raw closes, and explicit resolution of rights and security conversions."
        ),
    }
    manifest_target.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Archive primary B3 corporate events.")
    parser.add_argument("--prices", default="data/prices_b3_cotahist_price_return_only_2011_2025.csv")
    parser.add_argument("--mapping", default="data/b3_historical_cvm_ticker_map_2012_2025.csv")
    parser.add_argument("--events", default="data/b3_primary_corporate_events_2011_2025.csv")
    parser.add_argument("--coverage", default="data/b3_primary_event_coverage_2011_2025.csv")
    parser.add_argument("--manifest", default="data/b3_primary_events_2011_2025_manifest.json")
    parser.add_argument("--issuer-limit", type=int)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    result = archive_primary_events(
        args.prices, args.mapping, args.events, args.coverage, args.manifest, args.issuer_limit, args.resume
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
