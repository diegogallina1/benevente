"""Typed LLM boundary. The default mock is deterministic and API-free."""
from __future__ import annotations
import json
import os
from typing import Literal
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from config import SystemConfig


class MacroOutput(BaseModel):
    macro_summary: str = Field(max_length=240)
    equity_allocation_cap: float = Field(ge=0.10, le=0.90)
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]


class AssetScore(BaseModel):
    ticker: str
    confidence_score: float = Field(ge=-1.0, le=1.0)
    rationale: str = Field(max_length=120)


class SelectionOutput(BaseModel):
    scores: list[AssetScore]


class MockLLMAgents:
    def __init__(self, config: SystemConfig) -> None:
        self.config = config

    def macro(self, selic_rate: float, ipca_rate: float) -> MacroOutput:
        if selic_rate > 0.12:
            cap, risk = 0.40, "HIGH"
        elif selic_rate < 0.09:
            cap, risk = 0.80, "LOW"
        else:
            cap, risk = 0.60, "MEDIUM"
        return MacroOutput(macro_summary=f"Selic {selic_rate:.1%}; IPCA {ipca_rate:.1%}.", equity_allocation_cap=cap, risk_level=risk)

    def select(self, historical_returns: pd.DataFrame) -> SelectionOutput:
        scores = []
        for ticker in historical_returns.columns:
            if ticker == "TITULO_CDI":
                score = 1.0
            else:
                annual_return = (1 + historical_returns[ticker]).prod() ** (252 / len(historical_returns)) - 1
                annual_vol = historical_returns[ticker].std(ddof=1) * np.sqrt(252)
                score = float(np.clip((annual_return - self.config.risk_free_rate_annual) / (2 * annual_vol + 1e-9), -1, 1))
            scores.append(AssetScore(ticker=ticker, confidence_score=score, rationale="Deterministic risk-adjusted momentum."))
        return SelectionOutput(scores=scores)


class OpenAIStructuredAgents(MockLLMAgents):
    """Optional OpenAI adapter; no request is made unless this class is selected.

    The optimizer remains the sole producer of portfolio weights. API output is
    parsed and validated with Pydantic before it can influence any optimization.
    """
    def __init__(self, config: SystemConfig, model: str | None = None) -> None:
        super().__init__(config)
        self.model = model or os.getenv("BENEVENTE_OPENAI_MODEL", "gpt-4o")

    def macro(self, selic_rate: float, ipca_rate: float) -> MacroOutput:
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is required to enable OpenAIStructuredAgents.")
        from openai import OpenAI
        schema = MacroOutput.model_json_schema()
        response = OpenAI().responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": "You are a Brazilian macro allocation analyst. Return only the requested JSON."},
                {"role": "user", "content": f"Selic={selic_rate:.2%}; IPCA={ipca_rate:.2%}. Set an equity cap from 0.10 to 0.90."},
            ],
            text={"format": {"type": "json_schema", "name": "macro_output", "schema": schema, "strict": True}},
        )
        return MacroOutput.model_validate(json.loads(response.output_text))
