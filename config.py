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
    llm_alpha_influence: float = 0.30
    initial_wealth: float = 100.0
    tickers: list[str] = field(default_factory=lambda: [
        "PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA", "WEGE3.SA",
        "RENT3.SA", "ABEV3.SA", "BBAS3.SA", "TITULO_CDI",
    ])

