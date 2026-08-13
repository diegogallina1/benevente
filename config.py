from dataclasses import dataclass, field


@dataclass(frozen=True)
class SystemConfig:
    transaction_cost: float = 0.0010
    slippage: float = 0.0005
    max_asset_weight: float = 0.15
    risk_aversion_gamma: float = 2.5
    rebalance_threshold: float = 0.03
    rolling_window_days: int = 252
    rebalance_days: int = 21
    risk_free_rate_annual: float = 0.105
    # Kept solely so archived v0.1 run metadata can still be read. It has no
    # effect on allocation and must not be used by new experiments.
    llm_alpha_influence: float = 0.0
    signal_alpha_influence: float = 0.30
    value_quality_influence: float = 0.35
    initial_wealth: float = 100.0
    initial_portfolio_value_brl: float = 1_000_000.0
    cdi_bcb_series: int = 12
    selic_bcb_series: int = 432
    ipca_bcb_series: int = 433
    min_market_cap_brl: float = 2_000_000_000
    min_free_cash_flow_yield: float = 0.02
    min_roic: float = 0.08
    min_roe: float = 0.08
    max_debt_to_ebitda: float = 3.0
    min_interest_coverage: float = 2.0
    max_position_adv_participation: float = 0.05
    tickers: list[str] = field(default_factory=lambda: [
        "PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA", "WEGE3.SA",
        "RENT3.SA", "ABEV3.SA", "BBAS3.SA", "TITULO_CDI",
    ])
