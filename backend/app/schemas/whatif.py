"""What-if simulation contracts.

The response is the simulator's own ``WhatIfResult`` model, re-used verbatim.
Every number in it — probabilities, SHAP comparisons, ranking scores — is
computed by the locked Step 5 engine, so re-declaring the shape here would
create a second copy of a contract the backend does not own.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from agent.models.whatif import WhatIfResult

# Re-exported under an API-facing name for the OpenAPI schema.
WhatIfResponse = WhatIfResult


class CustomScenarioRequest(BaseModel):
    """A caller-supplied scenario, for changes the catalogue deliberately omits.

    The main case is a price change with a real, business-approved amount: the
    catalogue refuses to invent one, but a caller who has an approved offer can
    simulate it. It passes through exactly the same validation as a catalogue
    scenario, so an unknown feature or an impossible value is still rejected.
    """

    scenario_id: str = Field(..., min_length=1, examples=["approved_discount"])
    scenario_name: str = Field(..., min_length=1, examples=["Approved 10 EUR Monthly Discount"])
    changed_features: dict[str, Any] = Field(
        ..., min_length=1, examples=[{"MonthlyCharges": 19.85}]
    )
    strategy_id: str = Field(..., min_length=1, examples=["PRICING_VALUE"])
    rationale: str = Field(..., min_length=1)
    description: str = ""


class WhatIfRequest(BaseModel):
    """Request body for ``POST /api/what-if``."""

    customer_id: str = Field(..., min_length=1, examples=["7590-VHVEG"])
    scenario_ids: list[str] | None = Field(
        default=None,
        description=(
            "Catalogue scenarios to evaluate. Omit to evaluate every applicable "
            "catalogue scenario."
        ),
        examples=[["annual_contract", "two_year_contract"]],
    )
    custom_scenarios: list[CustomScenarioRequest] = Field(
        default_factory=list,
        description="Additional caller-defined scenarios, validated identically.",
    )
    use_llm: bool = Field(
        default=True,
        description=(
            "Let the configured LLM interpret the results. The AI never alters a "
            "computed number; with no LLM configured the deterministic "
            "interpretation is used instead."
        ),
    )

    @model_validator(mode="after")
    def _reject_duplicate_scenario_ids(self) -> "WhatIfRequest":
        """Duplicate ids would produce two indistinguishable rows in the ranking."""
        ids = list(self.scenario_ids or []) + [s.scenario_id for s in self.custom_scenarios]
        duplicates = {value for value in ids if ids.count(value) > 1}
        if duplicates:
            raise ValueError(f"Duplicate scenario id(s): {sorted(duplicates)}")
        return self


__all__ = ["CustomScenarioRequest", "WhatIfRequest", "WhatIfResponse"]
