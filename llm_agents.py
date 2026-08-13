"""Typed LLM boundary. The default mock is deterministic and API-free."""
from __future__ import annotations
import json
import os
from typing import Literal
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from config import SystemConfig
from fundamentals import FundamentalSnapshot


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


class ValueResearchOutput(BaseModel):
    ticker: str
    verdict: Literal["APPROVE", "WATCH", "REJECT"]
    confidence_score: float = Field(ge=-1.0, le=1.0)
    investment_horizon_years: Literal[2, 5]
    thesis: str = Field(max_length=500)
    key_risks: list[str] = Field(min_length=1, max_length=4)
    requires_human_review: bool = True


class MockLLMAgents:
    """Compatibility shell for the optional narrative adapter.

    Allocation signals moved to ``signals.DeterministicSignalEngine``.  This
    object is not imported by the backtest engine and cannot supply a weight or
    an optimization score.
    """
    def __init__(self, config: SystemConfig) -> None:
        self.config = config


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

    def review_value_candidate(self, snapshot: FundamentalSnapshot, horizon_years: int) -> ValueResearchOutput:
        """Review supplied facts only; it cannot override deterministic hard filters."""
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is required to enable OpenAIStructuredAgents.")
        if horizon_years not in (2, 5):
            raise ValueError("horizon_years must be 2 or 5")
        from openai import OpenAI
        response = OpenAI().responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": (
                    "You are a skeptical long-term value-investing research reviewer. Use only the supplied JSON facts. "
                    "Do not provide portfolio weights, price targets, or claims of guaranteed return. "
                    "Return the required JSON and set requires_human_review=true."
                )},
                {"role": "user", "content": json.dumps({"horizon_years": horizon_years, "fundamental_snapshot": snapshot.model_dump(mode="json")})},
            ],
            text={"format": {"type": "json_schema", "name": "value_research_output",
                              "schema": ValueResearchOutput.model_json_schema(), "strict": True}},
        )
        output = ValueResearchOutput.model_validate(json.loads(response.output_text))
        if output.ticker != snapshot.ticker:
            raise ValueError("LLM response ticker does not match supplied candidate")
        return output
