"""Atualiza o acompanhamento determinístico da carteira-sombra de 2026.

O programa não seleciona ativos, não altera pesos e não chama um modelo de
linguagem. Ele marca a mercado uma decisão anual já registrada, calcula CDI e
comparadores e grava um documento público encadeado por SHA-256.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from bisect import bisect_right
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
BCB_CDI_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados"
USER_AGENT = "Benevente-Research-Monitor/1.0 (+https://github.com/diegogallina1/benevente)"


class LiveDataError(RuntimeError):
    """Falha que impede publicar uma atualização íntegra."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _get_json(url: str, params: dict[str, str | int], timeout: int = 30) -> tuple[Any, str]:
    request = Request(f"{url}?{urlencode(params)}", headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - URLs are constants
        raw = response.read()
    return json.loads(raw.decode("utf-8")), hashlib.sha256(raw).hexdigest()


def fetch_yahoo_adjusted_close(ticker: str, start: date, end: date) -> tuple[dict[str, float], str]:
    """Baixa fechamento ajustado. ``end`` é inclusivo para a interface pública."""

    period1 = int(datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc).timestamp())
    period2 = int(
        datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc).timestamp()
    )
    payload, raw_sha256 = _get_json(
        YAHOO_CHART_URL.format(ticker=ticker),
        {
            "period1": period1,
            "period2": period2,
            "interval": "1d",
            "events": "history",
            "includeAdjustedClose": "true",
        },
    )
    try:
        result = payload["chart"]["result"][0]
        timestamps = result["timestamp"]
        adjusted = result["indicators"]["adjclose"][0]["adjclose"]
    except (KeyError, IndexError, TypeError) as exc:
        detail = payload.get("chart", {}).get("error") if isinstance(payload, dict) else None
        raise LiveDataError(f"Yahoo não retornou série válida para {ticker}: {detail}") from exc

    points: dict[str, float] = {}
    for timestamp, value in zip(timestamps, adjusted, strict=False):
        if value is None or not math.isfinite(float(value)) or float(value) <= 0:
            continue
        day = datetime.fromtimestamp(int(timestamp), tz=timezone.utc).date().isoformat()
        points[day] = float(value)
    if len(points) < 2:
        raise LiveDataError(f"Série insuficiente para {ticker}: {len(points)} observações")
    return points, raw_sha256


def fetch_bcb_cdi(start: date, end: date) -> tuple[dict[str, float], str]:
    """Baixa a taxa CDI diária oficial (SGS 12), em percentual ao dia."""

    payload, raw_sha256 = _get_json(
        BCB_CDI_URL,
        {
            "formato": "json",
            "dataInicial": start.strftime("%d/%m/%Y"),
            "dataFinal": end.strftime("%d/%m/%Y"),
        },
    )
    rates: dict[str, float] = {}
    for row in payload:
        try:
            day = datetime.strptime(row["data"], "%d/%m/%Y").date().isoformat()
            value = float(str(row["valor"]).replace(",", ".")) / 100.0
        except (KeyError, TypeError, ValueError) as exc:
            raise LiveDataError(f"Registro CDI inválido: {row!r}") from exc
        if not math.isfinite(value) or value <= -1:
            raise LiveDataError(f"Taxa CDI inválida em {day}: {value}")
        rates[day] = value
    if len(rates) < 2:
        raise LiveDataError(f"Série CDI insuficiente: {len(rates)} observações")
    return rates, raw_sha256


def _level_from_rates(rates: dict[str, float]) -> dict[str, float]:
    level = 1.0
    levels: dict[str, float] = {}
    for day in sorted(rates):
        level *= 1.0 + rates[day]
        levels[day] = level
    return levels


def _value_on_or_before(series: dict[str, float], day: str) -> float:
    dates = sorted(series)
    position = bisect_right(dates, day) - 1
    if position < 0:
        raise LiveDataError(f"Não existe observação até {day}")
    return series[dates[position]]


def _maximum_drawdown(values: list[float]) -> float:
    peak = -math.inf
    worst = 0.0
    for value in values:
        peak = max(peak, value)
        worst = min(worst, value / peak - 1.0)
    return worst


B2_CONFIG = {
    "alert_drawdown": 0.12,
    "severe_drawdown": 0.22,
    "alert_volatility": 0.40,
    "severe_volatility": 0.60,
    "alert_equity_cap": 0.50,
    "severe_equity_cap": 0.35,
    "recovery_days": 10,
    "cost_bps": 10.0,
    "volatility_window": 20,
    "peak_window": 126,
}
MONITORING_PROTOCOL_SHA256 = "15d6f7957c35baaf551f866e1f76998006d3443b908f8d2f6795846e0493f8cd"
B2_PROTOCOL_SHA256 = "d1f37a440f24421e0df32f304ee0683c6de04ed9417d0cb014a0bfc7309e80e4"


def _sample_volatility(returns: list[float]) -> float | None:
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((value - mean) ** 2 for value in returns) / (len(returns) - 1)
    return math.sqrt(variance) * math.sqrt(252.0)


def target_allocation(
    holdings: list[dict[str, Any]], base_equity_weight: float, target_equity_weight: float
) -> list[dict[str, Any]]:
    """Escala a cesta proporcionalmente e fecha o livro em 100% com CDI."""

    if base_equity_weight <= 0 or not 0 <= target_equity_weight <= 1:
        raise LiveDataError("Exposição-alvo inválida")
    rows = [
        {
            "ticker": str(item["ticker"]),
            "weight": round(float(item["weight"]) / base_equity_weight * target_equity_weight, 12),
        }
        for item in holdings
    ]
    rows.append({"ticker": "CDI", "weight": round(1.0 - target_equity_weight, 12)})
    difference = 1.0 - sum(row["weight"] for row in rows)
    rows[-1]["weight"] = round(rows[-1]["weight"] + difference, 12)
    if not math.isclose(sum(row["weight"] for row in rows), 1.0, abs_tol=1e-9):
        raise LiveDataError("A alocação operacional não soma 100%")
    return rows


def _advance_risk_state(state: int, calmer_days: int, tradable: int) -> tuple[int, int]:
    if tradable > state:
        return tradable, 0
    if tradable < state:
        calmer_days += 1
        if calmer_days >= B2_CONFIG["recovery_days"]:
            return state - 1, 0
        return state, calmer_days
    return state, 0


def apply_benevente2_overlay(
    rows: list[dict[str, Any]], base_equity_weight: float
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Aplica a política registrada usando somente o fechamento anterior."""

    states: list[int] = []
    raw_states: list[int] = []
    decisions: list[dict[str, Any]] = []
    market_returns: list[float] = []
    previous_market: float | None = None
    state = 0
    calmer_days = 0
    for index, row in enumerate(rows):
        market = float(row["ibovespa_price"])
        market_returns.append(0.0 if previous_market is None else market / previous_market - 1.0)
        previous_market = market
        window_start = max(0, index - B2_CONFIG["peak_window"] + 1)
        peak = max(float(item["ibovespa_price"]) for item in rows[window_start : index + 1])
        drawdown = market / peak - 1.0
        volatility = None
        if index + 1 >= B2_CONFIG["volatility_window"]:
            volatility = _sample_volatility(
                market_returns[index - B2_CONFIG["volatility_window"] + 1 : index + 1]
            )
        raw = 0
        if drawdown <= -B2_CONFIG["alert_drawdown"] or (
            volatility is not None and volatility >= B2_CONFIG["alert_volatility"]
        ):
            raw = 1
        if drawdown <= -B2_CONFIG["severe_drawdown"] or (
            volatility is not None and volatility >= B2_CONFIG["severe_volatility"]
        ):
            raw = 2
        raw_states.append(raw)

        tradable = raw_states[index - 1] if index else 0
        previous_state = state
        state, calmer_days = _advance_risk_state(state, calmer_days, tradable)
        states.append(state)
        row["market_drawdown"] = round(drawdown, 12)
        row["market_volatility"] = round(volatility, 12) if volatility is not None else None
        row["risk_state"] = state
        row["stress_at_close"] = raw
        row["tradable_stress"] = tradable
        if index == 0 or state != previous_state:
            evidence = rows[index - 1] if index else row
            trigger = []
            evidence_drawdown = evidence.get("market_drawdown")
            evidence_volatility = evidence.get("market_volatility")
            if evidence_drawdown is not None:
                if evidence_drawdown <= -B2_CONFIG["severe_drawdown"]:
                    trigger.append("queda severa")
                elif evidence_drawdown <= -B2_CONFIG["alert_drawdown"]:
                    trigger.append("queda de alerta")
            if evidence_volatility is not None:
                if evidence_volatility >= B2_CONFIG["severe_volatility"]:
                    trigger.append("volatilidade severa")
                elif evidence_volatility >= B2_CONFIG["alert_volatility"]:
                    trigger.append("volatilidade de alerta")
            decisions.append({
                "effective_on": row["date"],
                "observed_on": evidence["date"] if index else None,
                "from_state": previous_state if index else None,
                "to_state": state,
                "target_equity_weight": (
                    base_equity_weight if state == 0 else
                    min(base_equity_weight, B2_CONFIG["alert_equity_cap"] if state == 1 else B2_CONFIG["severe_equity_cap"])
                ),
                "observed_market_drawdown": evidence_drawdown,
                "observed_market_volatility": evidence_volatility,
                "reason": " e ".join(trigger) if trigger else ("início do ciclo" if index == 0 else "recuperação após dez pregões mais calmos"),
            })

    b2_level = 100.0
    previous_b1 = 100.0
    previous_cdi = 100.0
    previous_equity = base_equity_weight
    total_turnover = 0.0
    for index, row in enumerate(rows):
        state = states[index]
        desired_equity = base_equity_weight
        if state == 1:
            desired_equity = min(desired_equity, B2_CONFIG["alert_equity_cap"])
        elif state == 2:
            desired_equity = min(desired_equity, B2_CONFIG["severe_equity_cap"])
        turnover = abs(desired_equity - previous_equity) if index else 0.0
        cost = turnover * B2_CONFIG["cost_bps"] / 10_000.0
        b1_return = float(row["portfolio"]) / previous_b1 - 1.0 if index else 0.0
        cdi_return = float(row["cdi"]) / previous_cdi - 1.0 if index else 0.0
        multiplier = desired_equity / base_equity_weight if base_equity_weight else 0.0
        b2_return = cdi_return + multiplier * (b1_return - cdi_return) - cost
        b2_level *= 1.0 + b2_return
        row["benevente2"] = round(b2_level, 8)
        row["benevente2_equity_weight"] = round(desired_equity, 12)
        row["overlay_turnover"] = round(turnover, 12)
        total_turnover += turnover
        previous_b1 = float(row["portfolio"])
        previous_cdi = float(row["cdi"])
        previous_equity = desired_equity

    labels = {0: "normal", 1: "alerta", 2: "severo"}
    next_state, next_calmer_days = _advance_risk_state(state, calmer_days, raw_states[-1])
    next_equity = base_equity_weight
    if next_state == 1:
        next_equity = min(next_equity, B2_CONFIG["alert_equity_cap"])
    elif next_state == 2:
        next_equity = min(next_equity, B2_CONFIG["severe_equity_cap"])
    return rows, {
        "configuration": B2_CONFIG,
        "current_risk_state": labels[states[-1]],
        "current_equity_weight": rows[-1]["benevente2_equity_weight"],
        "next_session_risk_state": labels[next_state],
        "next_session_equity_weight": next_equity,
        "calmer_days_accumulated": next_calmer_days,
        "overlay_turnover": round(total_turnover, 12),
        "risk_decisions": decisions,
        "activation_date": "2026-08-20",
        "before_activation": "reconstrução retrospectiva",
        "after_activation": "acompanhamento versionado",
    }


def build_live_document(
    decision: dict[str, Any],
    market_series: dict[str, dict[str, float]],
    cdi_rates: dict[str, float],
    raw_hashes: dict[str, str],
    previous: dict[str, Any] | None = None,
    generated_at: datetime | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Calcula buy-and-hold com pesos iniciais, sem rebalanceamento intranual."""

    holdings = decision.get("holdings") or []
    if not holdings:
        raise LiveDataError("A decisão não contém ativos")
    decision_date = str(decision["decision_date"])
    equity_weight = sum(float(item["weight"]) for item in holdings)
    cdi_weight = float(decision["cdi_weight"])
    if not math.isclose(equity_weight + cdi_weight, 1.0, abs_tol=1e-8):
        raise LiveDataError("Os pesos da decisão não somam 100%")

    required = [str(item["ticker"]) for item in holdings] + ["BOVA11", "IBOVESPA"]
    missing = sorted(ticker for ticker in required if not market_series.get(ticker))
    if missing:
        raise LiveDataError(f"Séries ausentes: {', '.join(missing)}")

    common_dates = set(market_series[required[0]])
    for ticker in required[1:]:
        common_dates &= set(market_series[ticker])
    common_dates &= set(cdi_rates)
    timeline = sorted(day for day in common_dates if day >= decision_date)
    if len(timeline) < 2:
        raise LiveDataError("Não há ao menos duas datas comuns depois da decisão")
    start_day, through = timeline[0], timeline[-1]
    if start_day != decision_date:
        raise LiveDataError(f"A primeira data comum é {start_day}, não {decision_date}")
    # Provedores públicos podem devolver diferenças de ponto flutuante no mesmo
    # conjunto de sessões. Sem uma nova data comum, preservar o registro evita
    # commits artificiais; qualquer revisão entra junto com a sessão seguinte.
    if previous and previous.get("through") == through and not force:
        return previous

    cdi_levels = _level_from_rates(cdi_rates)
    cdi_start = _value_on_or_before(cdi_levels, start_day)
    starts = {ticker: market_series[ticker][start_day] for ticker in required}
    series: list[dict[str, Any]] = []
    for day in timeline:
        equity_value = sum(
            float(item["weight"])
            * market_series[str(item["ticker"])][day]
            / starts[str(item["ticker"])]
            for item in holdings
        )
        cdi_relative = _value_on_or_before(cdi_levels, day) / cdi_start
        portfolio_relative = equity_value + cdi_weight * cdi_relative
        series.append(
            {
                "date": day,
                "portfolio": round(portfolio_relative * 100.0, 8),
                "cdi": round(cdi_relative * 100.0, 8),
                "bova11": round(market_series["BOVA11"][day] / starts["BOVA11"] * 100.0, 8),
                "ibovespa_price": round(
                    market_series["IBOVESPA"][day] / starts["IBOVESPA"] * 100.0, 8
                ),
            }
        )

    holding_rows = []
    for item in holdings:
        ticker = str(item["ticker"])
        start_price = market_series[ticker][start_day]
        last_price = market_series[ticker][through]
        total_return = last_price / start_price - 1.0
        holding_rows.append(
            {
                "ticker": ticker,
                "weight": float(item["weight"]),
                "start_adjusted_close": round(start_price, 8),
                "last_adjusted_close": round(last_price, 8),
                "total_return": round(total_return, 12),
                "portfolio_contribution": round(float(item["weight"]) * total_return, 12),
                "source_last_date": through,
            }
        )

    series, b2 = apply_benevente2_overlay(series, equity_weight)
    b1_target = target_allocation(holdings, equity_weight, equity_weight)
    b2_target = target_allocation(
        holdings, equity_weight, float(b2["next_session_equity_weight"])
    )
    b1_by_ticker = {row["ticker"]: row["weight"] for row in b1_target}
    for row in b2_target:
        row["difference_from_benevente1"] = round(
            row["weight"] - b1_by_ticker[row["ticker"]], 12
        )
        row["amount_for_brl_100k"] = round(row["weight"] * 100_000.0, 2)
    for decision_row in b2["risk_decisions"]:
        decision_row["target_allocation"] = target_allocation(
            holdings, equity_weight, float(decision_row["target_equity_weight"])
        )
    last = series[-1]
    equity_last = sum(row["weight"] * (1.0 + row["total_return"]) for row in holding_rows)
    summary = {
        "portfolio_return": round(last["portfolio"] / 100.0 - 1.0, 12),
        "benevente2_reconstructed_return": round(last["benevente2"] / 100.0 - 1.0, 12),
        "portfolio_value_brl": round(100_000.0 * last["portfolio"] / 100.0, 2),
        "equity_sleeve_return": round(equity_last / equity_weight - 1.0, 12),
        "cdi_return": round(last["cdi"] / 100.0 - 1.0, 12),
        "bova11_return": round(last["bova11"] / 100.0 - 1.0, 12),
        "ibovespa_price_return": round(last["ibovespa_price"] / 100.0 - 1.0, 12),
        "maximum_drawdown": round(_maximum_drawdown([row["portfolio"] for row in series]), 12),
        "benevente2_maximum_drawdown": round(
            _maximum_drawdown([row["benevente2"] for row in series]), 12
        ),
    }
    core = {
        "schema_version": "1.0.0",
        "strategy": "Benevente 2",
        "reference_strategy": "Benevente 1",
        "status": "carteira_sombra_acompanhamento_corrente",
        "decision_date": decision_date,
        "protocol_version": "monitoramento-diario-1.0.0",
        "protocol_registered_at": "2026-08-23",
        "protocol_sha256": MONITORING_PROTOCOL_SHA256,
        "benevente2_protocol_sha256": B2_PROTOCOL_SHA256,
        "through": through,
        "currency": "BRL",
        "initial_capital_brl": 100_000.0,
        "price_basis": "fechamento_ajustado_fonte_publica_secundaria",
        "holdings": holding_rows,
        "cdi_weight": cdi_weight,
        "summary": summary,
        "portfolio_definitions": {
            "benevente1": {
                "rule": "pesos de janeiro mantidos até a revisão anual",
                "target_allocation": [
                    {**row, "amount_for_brl_100k": round(row["weight"] * 100_000.0, 2)}
                    for row in b1_target
                ],
            },
            "benevente2": {
                "rule": "mesma cesta com exposição definida pelo estado de risco para a próxima sessão",
                "state_for_next_session": b2["next_session_risk_state"],
                "target_allocation": b2_target,
            },
        },
        "benevente2_overlay": b2,
        "series": series,
        "sources": {
            "equities_and_bova11": "Yahoo Finance Chart API, fechamento ajustado; fonte pública secundária",
            "ibovespa": "Yahoo Finance Chart API (^BVSP), índice de preço",
            "cdi": "Banco Central do Brasil, SGS série 12",
            "raw_response_sha256": dict(sorted(raw_hashes.items())),
        },
        "data_quality": {
            "provisional": True,
            "corporate_actions": (
                "O fechamento ajustado incorpora os ajustes publicados pelo provedor secundário. "
                "A conciliação integral com eventos B3/CVM ainda não foi concluída."
            ),
            "missing_tickers": [],
            "interpretation": (
                "Acompanhamento da decisão de 02/01/2026. Não é validação prospectiva porque "
                "o método foi refinado durante 2026. A trajetória do Benevente 2 anterior a "
                "20/08/2026 é reconstrução retrospectiva."
            ),
        },
    }
    content_sha256 = _sha256(core)
    if previous and previous.get("content_sha256") == content_sha256:
        return previous

    now = generated_at or datetime.now(timezone.utc)
    document = {
        **core,
        "content_sha256": content_sha256,
        "updated_at_utc": now.astimezone(timezone.utc).replace(microsecond=0).isoformat(),
        "previous_record_sha256": previous.get("record_sha256") if previous else None,
    }
    document["record_sha256"] = _sha256(document)
    return document


def update(
    decision_path: Path, output_path: Path, as_of: date | None = None, force: bool = False
) -> dict[str, Any]:
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    previous = json.loads(output_path.read_text(encoding="utf-8")) if output_path.exists() else None
    start = datetime.strptime(decision["decision_date"], "%Y-%m-%d").date()
    end = as_of or date.today()
    market_series: dict[str, dict[str, float]] = {}
    raw_hashes: dict[str, str] = {}
    for item in decision["holdings"]:
        ticker = str(item["ticker"])
        market_series[ticker], raw_hashes[f"{ticker}.SA"] = fetch_yahoo_adjusted_close(
            f"{ticker}.SA", start, end
        )
    market_series["BOVA11"], raw_hashes["BOVA11.SA"] = fetch_yahoo_adjusted_close(
        "BOVA11.SA", start, end
    )
    market_series["IBOVESPA"], raw_hashes["^BVSP"] = fetch_yahoo_adjusted_close(
        "%5EBVSP", start, end
    )
    cdi_rates, raw_hashes["BCB_SGS_12"] = fetch_bcb_cdi(start, end)
    document = build_live_document(
        decision, market_series, cdi_rates, raw_hashes, previous, force=force
    )
    if document is not previous:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decision", type=Path, default=Path("web/current_decision_2026.json"))
    parser.add_argument("--output", type=Path, default=Path("web/live_performance.json"))
    parser.add_argument("--as-of", type=lambda value: datetime.strptime(value, "%Y-%m-%d").date())
    parser.add_argument("--force", action="store_true", help="Publica mudança de contrato sem nova sessão")
    args = parser.parse_args()
    document = update(args.decision, args.output, args.as_of, args.force)
    print(
        f"Acompanhamento até {document['through']}: "
        f"{document['summary']['portfolio_return']:+.2%}; "
        f"registro {document['record_sha256'][:12]}"
    )


if __name__ == "__main__":
    main()
