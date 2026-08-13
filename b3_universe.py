"""Build a dated B3 instrument universe from the official COTAHIST file.

The B3 historical quotation file records every instrument traded in the cash
market.  It is deliberately broader than a stock-selection universe: ETFs,
BDRs, FIIs, units and other instruments are retained so coverage can be
reported honestly.  Asset eligibility is a later decision that also requires
the appropriate fundamentals, liquidity and mandate.
"""
from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pandas as pd


def _field(line: str, start: int, end: int) -> str:
    """Read the 1-indexed inclusive COTAHIST fixed-width field."""
    return line[start - 1:end].strip()


def parse_cotahist(path: str | Path) -> pd.DataFrame:
    """Parse COTAHIST daily records needed for a point-in-time universe."""
    archive_path = Path(path)
    with ZipFile(archive_path) as archive:
        name = next((item for item in archive.namelist() if item.upper().endswith(".TXT")), None)
        if name is None:
            raise ValueError("COTAHIST archive has no TXT file.")
        with archive.open(name) as source:
            lines = (raw.decode("latin1").rstrip("\r\n") for raw in source)
            rows = []
            for line in lines:
                if len(line) < 245 or _field(line, 1, 2) != "01":
                    continue
                rows.append({
                    "trade_date": _field(line, 3, 10),
                    "bdi_code": _field(line, 11, 12),
                    "ticker_raw": _field(line, 13, 24),
                    "market_type": _field(line, 25, 27),
                    "issuer_name": _field(line, 28, 39),
                    "specification": _field(line, 40, 49),
                    "currency": _field(line, 53, 56),
                    "close_price_brl": int(_field(line, 109, 121) or 0) / 100,
                    "trade_count": int(_field(line, 148, 152) or 0),
                    "quantity": int(_field(line, 153, 170) or 0),
                    "traded_value_brl": int(_field(line, 171, 188) or 0) / 100,
                    "isin": _field(line, 231, 242),
                })
    frame = pd.DataFrame(rows)
    if frame.empty:
        raise ValueError("COTAHIST archive has no daily quotation records.")
    frame["trade_date"] = pd.to_datetime(frame.trade_date, format="%Y%m%d", errors="coerce")
    return frame.dropna(subset=["trade_date", "ticker_raw"])


def classify_instrument(specification: str, market_type: str, issuer_name: str = "") -> str:
    """Conservative B3 classification from official COTAHIST descriptors."""
    spec = str(specification).upper().strip()
    issuer = str(issuer_name).upper().strip()
    if market_type != "010":
        return "other"
    if "FII" in spec or "FIAGRO" in spec or issuer.startswith(("FII ", "FIAGRO ")):
        return "fii"
    # BDR specifications are DR1/DR2/DR3/DRN/DRE, never inferred from the
    # issuer name (e.g. "RAIA DROGASIL" must remain an equity).
    if spec.startswith("DR"):
        return "bdr"
    # `CI` is also used by FIIs.  The issuer name disambiguates that case;
    # generic CI remains a fund/ETF-like instrument until a richer B3 master
    # file is attached.
    if "ETF" in spec or "CI" in spec:
        return "etf"
    if any(marker in spec for marker in ("ON", "PN", "PNA", "PNB", "PNC", "UNT")):
        return "equity"
    return "other"


def build_universe_snapshot(quotations: pd.DataFrame, decision_date: str | pd.Timestamp,
                            liquidity_days: int = 60) -> pd.DataFrame:
    """Freeze all cash-market B3 instruments known on or before a decision date."""
    decision = pd.Timestamp(decision_date).normalize()
    eligible_dates = quotations.loc[quotations.trade_date <= decision, "trade_date"]
    if eligible_dates.empty:
        raise ValueError("No COTAHIST observations are available on or before decision_date.")
    last_trade = eligible_dates.max()
    sessions = sorted(quotations.loc[quotations.trade_date <= last_trade, "trade_date"].unique())[-liquidity_days:]
    liquid_window = quotations[quotations.trade_date.isin(sessions)].copy()
    latest = quotations[quotations.trade_date == last_trade].copy()
    latest = latest[(latest.market_type == "010") & latest.ticker_raw.str.fullmatch(r"[A-Z0-9]{4,8}", na=False)].copy()
    if latest.empty:
        raise ValueError("No cash-market B3 instruments found for the latest available session.")
    liquidity = liquid_window.groupby("ticker_raw", as_index=False).agg(
        average_daily_value_brl=("traded_value_brl", "mean"),
        trading_days=("trade_date", "nunique"),
    )
    snapshot = latest.merge(liquidity, on="ticker_raw", how="left")
    snapshot["asset_class"] = [classify_instrument(spec, market, issuer)
                               for issuer, spec, market in zip(snapshot.issuer_name, snapshot.specification, snapshot.market_type)]
    snapshot["ticker"] = snapshot.ticker_raw + ".SA"
    snapshot["decision_date"] = decision.date().isoformat()
    snapshot["observed_at"] = last_trade.date().isoformat()
    snapshot["source"] = (
        f"B3 COTAHIST official annual file; last trading session {last_trade.date().isoformat()}; "
        f"{len(sessions)}-session average traded value"
    )
    columns = ["decision_date", "ticker", "ticker_raw", "asset_class", "issuer_name", "specification", "isin",
               "observed_at", "close_price_brl", "average_daily_value_brl", "trading_days", "trade_count", "quantity", "source"]
    return snapshot[columns].sort_values(["asset_class", "average_daily_value_brl", "ticker"], ascending=[True, False, True]).reset_index(drop=True)
