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
MONITORING_PROTOCOL_SHA256 = "763fd1c5487858ac580cd021b5c52abe35e4b04a0012b6a36516b19fba626b53"
B2_PROTOCOL_SHA256 = "d1f37a440f24421e0df32f304ee0683c6de04ed9417d0cb014a0bfc7309e80e4"


def _sample_volatility(returns: list[float]) -> float | None:
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((value - mean) ** 2 for value in returns) / (len(returns) - 1)
    return math.sqrt(variance) * math.sqrt(252.0)


def target_allocation(
    holdings: list[dict[str, Any]], base_equity_weight: float, target_equity_weight: float,
    exempt: tuple[str, ...] = ()
) -> list[dict[str, Any]]:
    """Escala a cesta proporcionalmente e fecha o livro em 100% com CDI.

    ``exempt`` lista instrumentos que a camada de proteção não toca. A política
    declarada isenta a perna global: o sinal de estresse é calculado sobre o
    Ibovespa, e cortar o fundo que existe justamente por não seguir o Ibovespa
    venderia o único ativo ao qual o sinal não se aplica. Sem esta lista, a
    camada escalaria tudo por igual e o livro publicado deixaria de ser o que o
    registro declara.
    """
    if base_equity_weight <= 0 or not 0 <= target_equity_weight <= 1:
        raise LiveDataError("Exposição-alvo inválida")
    rows = [
        {
            "ticker": str(item["ticker"]),
            "weight": round(
                float(item["weight"]) if str(item["ticker"]) in exempt
                else float(item["weight"]) / base_equity_weight * target_equity_weight, 12),
        }
        for item in holdings
    ]
    rows.append({"ticker": "CDI",
                 "weight": round(1.0 - sum(row["weight"] for row in rows), 12)})
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


def _desired_equity(base: float, state: int, config: dict[str, Any],
                    multipliers: tuple[float, float] | None) -> float:
    """A exposição-alvo de um estado, na forma que a política declara.

    O livro herdado da regra anterior expressa a camada como teto: no alerta a
    parcela em ações não passa de 50%. A escada declarada expressa como
    multiplicador por perfil: no alerta o conservador vai a 55% do próprio alvo,
    o arrojado a 85%. Não são a mesma regra e não podem compartilhar constante —
    aplicar o teto de 50% a um livro de 44% simplesmente não faz nada, e o
    acompanhamento diria estar protegido sem ter cortado um real.
    """
    if state == 0:
        return base
    if multipliers is not None:
        return base * (multipliers[0] if state == 1 else multipliers[1])
    cap = config["alert_equity_cap"] if state == 1 else config["severe_equity_cap"]
    return min(base, cap)


def apply_benevente2_overlay(
    rows: list[dict[str, Any]], base_equity_weight: float,
    config: dict[str, Any] | None = None,
    multipliers: tuple[float, float] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Aplica a política registrada usando somente o fechamento anterior."""
    config = config or B2_CONFIG

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
        window_start = max(0, index - config["peak_window"] + 1)
        peak = max(float(item["ibovespa_price"]) for item in rows[window_start : index + 1])
        drawdown = market / peak - 1.0
        volatility = None
        if index + 1 >= config["volatility_window"]:
            volatility = _sample_volatility(
                market_returns[index - config["volatility_window"] + 1 : index + 1]
            )
        raw = 0
        if drawdown <= -config["alert_drawdown"] or (
            volatility is not None and volatility >= config["alert_volatility"]
        ):
            raw = 1
        if drawdown <= -config["severe_drawdown"] or (
            volatility is not None and volatility >= config["severe_volatility"]
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
                if evidence_drawdown <= -config["severe_drawdown"]:
                    trigger.append("queda severa")
                elif evidence_drawdown <= -config["alert_drawdown"]:
                    trigger.append("queda de alerta")
            if evidence_volatility is not None:
                if evidence_volatility >= config["severe_volatility"]:
                    trigger.append("volatilidade severa")
                elif evidence_volatility >= config["alert_volatility"]:
                    trigger.append("volatilidade de alerta")
            decisions.append({
                "effective_on": row["date"],
                "observed_on": evidence["date"] if index else None,
                "from_state": previous_state if index else None,
                "to_state": state,
                "target_equity_weight": _desired_equity(base_equity_weight, state, config, multipliers),
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
        desired_equity = _desired_equity(base_equity_weight, state, config, multipliers)
        turnover = abs(desired_equity - previous_equity) if index else 0.0
        cost = turnover * config["cost_bps"] / 10_000.0
        b1_return = float(row["portfolio"]) / previous_b1 - 1.0 if index else 0.0
        cdi_return = float(row["cdi"]) / previous_cdi - 1.0 if index else 0.0
        multiplier = desired_equity / base_equity_weight if base_equity_weight else 0.0
        # O excesso sobre o caixa é decomposto por perna. A camada escala só o
        # doméstico; a perna global fica com o próprio excesso inteiro, porque a
        # política a declara isenta. A fórmula anterior escalava b1 − cdi por
        # inteiro, e cortava o fundo global junto com as ações num sinal que
        # não se aplica a ele. Com multiplicador 1 as duas formas coincidem.
        if index and "domestic" in row and "domestic" in rows[index - 1]:
            anterior = rows[index - 1]
            base = float(anterior["portfolio"])
            dom_contrib = (float(row["domestic"]) - float(anterior["domestic"])) / base
            glob_contrib = (float(row["global"]) - float(anterior["global"])) / base
            dom_share = float(anterior["domestic"]) / base
            glob_share = float(anterior["global"]) / base
            b2_return = (cdi_return
                         + multiplier * (dom_contrib - dom_share * cdi_return)
                         + (glob_contrib - glob_share * cdi_return)
                         - cost)
        else:
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
    # O alvo da próxima sessão sai da mesma regra que a exposição corrente. Aqui
    # ficou o teto fixo do livro antigo enquanto a série já usava o
    # multiplicador do perfil: no alerta, current_equity_weight dizia 55% do
    # alvo e next_session_equity_weight dizia "manter", no mesmo registro. A
    # alocação publicada para o próximo pregão, e o valor em reais dela, saíam
    # sem o corte que a série descrevia.
    next_equity = _desired_equity(base_equity_weight, next_state, config, multipliers)
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
    # A camada de proteção só move a parcela doméstica; a perna global entra no
    # livro, é marcada a mercado como qualquer outra posição, mas não é cortada.
    exempt = tuple(str(t) for t in decision.get("overlay_exempt", ()))
    exempt_weight = sum(float(i["weight"]) for i in holdings if str(i["ticker"]) in exempt)
    equity_weight = sum(float(item["weight"]) for item in holdings) - exempt_weight
    cdi_weight = float(decision["cdi_weight"])
    if not math.isclose(equity_weight + exempt_weight + cdi_weight, 1.0, abs_tol=1e-8):
        raise LiveDataError("Os pesos da decisão não somam 100%")

    required = [str(item["ticker"]) for item in holdings] + ["BOVA11", "IBOVESPA"]
    missing = sorted(ticker for ticker in required if not market_series.get(ticker))
    if missing:
        raise LiveDataError(f"Séries ausentes: {', '.join(missing)}")

    common_dates = set(market_series[required[0]])
    for ticker in required[1:]:
        common_dates &= set(market_series[ticker])
    common_dates &= set(cdi_rates)
    # Um pregão some da série publicada sempre que qualquer papel não tem preço
    # nele. Isso acontecia em silêncio e o arquivo saía com missing_tickers
    # vazio escrito no código. Agora cada papel conta quantos pregões derrubou,
    # e o total de sessões perdidas vai junto: dado que falta tem de aparecer
    # como falta, não como série mais curta com cara de completa.
    uniao = set()
    for ticker in required:
        uniao |= {day for day in market_series[ticker] if day >= decision_date}
    uniao |= {day for day in cdi_rates if day >= decision_date}
    faltas = {
        ticker: sorted(day for day in uniao if day not in market_series[ticker])
        for ticker in required
    }
    faltas = {ticker: dias for ticker, dias in faltas.items() if dias}
    sessoes_perdidas = sorted(day for day in uniao if day not in common_dates)
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
        # As duas pernas separadas, porque a camada de proteção só move uma. A
        # reconstrução do Benevente 2 precisa saber quanto do excesso veio do
        # doméstico, que ela escala, e quanto veio da perna global, que a
        # política declara isenta e ela não pode tocar.
        global_value = sum(
            float(item["weight"])
            * market_series[str(item["ticker"])][day]
            / starts[str(item["ticker"])]
            for item in holdings if str(item["ticker"]) in exempt
        )
        domestic_value = sum(
            float(item["weight"])
            * market_series[str(item["ticker"])][day]
            / starts[str(item["ticker"])]
            for item in holdings if str(item["ticker"]) not in exempt
        )
        equity_value = domestic_value + global_value
        cdi_relative = _value_on_or_before(cdi_levels, day) / cdi_start
        portfolio_relative = equity_value + cdi_weight * cdi_relative
        series.append(
            {
                "date": day,
                "portfolio": round(portfolio_relative * 100.0, 8),
                "domestic": round(domestic_value * 100.0, 8),
                "global": round(global_value * 100.0, 8),
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

    # Se a decisão declara a camada, ela manda. Sem isso o monitor aplicaria as
    # constantes do livro anterior a um livro que segue outra política.
    overlay = decision.get("overlay") or {}
    config = {**B2_CONFIG, **(overlay.get("config") or {})}
    multipliers = overlay.get("multipliers")
    multipliers = (float(multipliers[0]), float(multipliers[1])) if multipliers else None
    series, b2 = apply_benevente2_overlay(series, equity_weight, config, multipliers)
    b2["configuration"] = config
    if multipliers:
        b2["profile_multipliers"] = {"alerta": multipliers[0], "severo": multipliers[1]}
    b1_target = target_allocation(holdings, equity_weight, equity_weight, exempt)
    b2_target = target_allocation(
        holdings, equity_weight, float(b2["next_session_equity_weight"]), exempt
    )
    b1_by_ticker = {row["ticker"]: row["weight"] for row in b1_target}
    for row in b2_target:
        row["difference_from_benevente1"] = round(
            row["weight"] - b1_by_ticker[row["ticker"]], 12
        )
        row["amount_for_brl_100k"] = round(row["weight"] * 100_000.0, 2)
    for decision_row in b2["risk_decisions"]:
        decision_row["target_allocation"] = target_allocation(
            holdings, equity_weight, float(decision_row["target_equity_weight"]), exempt
        )
    last = series[-1]
    equity_last = sum(row["weight"] * (1.0 + row["total_return"]) for row in holding_rows)
    summary = {
        "portfolio_return": round(last["portfolio"] / 100.0 - 1.0, 12),
        "benevente2_reconstructed_return": round(last["benevente2"] / 100.0 - 1.0, 12),
        "portfolio_value_brl": round(100_000.0 * last["portfolio"] / 100.0, 2),
        # O numerador soma todas as posições, inclusive a perna global; o
        # denominador precisa somar os mesmos pesos. Dividir por equity_weight,
        # que já teve a parcela isenta subtraída, publicava ~26% de retorno da
        # perna de ações em todos os perfis: era 1,25 × (1 + r) − 1, não r.
        "equity_sleeve_return": round(equity_last / (equity_weight + exempt_weight) - 1.0, 12),
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
        "protocol_version": "monitoramento-diario-1.1.0",
        "protocol_registered_at": "2026-09-02",
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
            "missing_tickers": [
                {"ticker": ticker, "missing_sessions": len(dias), "first": dias[0], "last": dias[-1]}
                for ticker, dias in sorted(faltas.items())
            ],
            "dropped_sessions": len(sessoes_perdidas),
            "dropped_sessions_note": (
                "Pregões em que algum papel não tinha preço na fonte e que por isso "
                "saíram da série inteira. Zero é o esperado; qualquer outro número é "
                "buraco no dado, não no mercado."),
            "interpretation": (
                "Marcação a mercado do que a política vigente teria montado em 02/01/2026 com os "
                "dados daquele dia. As séries de 2026 foram reconstruídas em agosto de 2026 e "
                "publicadas a partir de 26/08/2026; não são validação prospectiva. A primeira "
                "amostra confirmatória começa no primeiro pregão de 2027."
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
