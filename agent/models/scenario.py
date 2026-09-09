"""What-if scenario definitions.

A scenario is a *hypothetical customer profile*, not an action. It says "suppose
this customer's Contract value were 'One year' instead of 'Month-to-month'" and
lets us ask the already-trained model what it would predict. It does not claim
that offering a one-year contract would cause that change.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# Attached to every simulator output. Stated verbatim so it cannot drift.
WHATIF_DISCLAIMER = "Model-based what-if estimate — not a causal prediction."


class Scenario(BaseModel):
    """One hypothetical profile change, tied to a retention strategy."""

    model_config = ConfigDict(frozen=True)

    scenario_id: str
    scenario_name: str
    description: str

    # Feature name -> hypothetical value. Validated against the fitted
    # preprocessor's learned domain before anything is predicted.
    changed_features: dict[str, Any]

    # Why this hypothetical profile is worth evaluating at all.
    rationale: str

    # The Step 4 catalogue strategy this scenario represents.
    strategy_id: str

    # Scenario-specific caveats, on top of the standard what-if limitations.
    limitations: tuple[str, ...] = ()

    # Current profile values required for the scenario to make sense, e.g.
    # {"Contract": ("Month-to-month",)} — there is no point simulating a move to
    # a one-year contract for someone already on one.
    applicable_when: dict[str, tuple[str, ...]] = Field(default_factory=dict)

    @property
    def changed_feature_names(self) -> tuple[str, ...]:
        return tuple(self.changed_features)


class UnsimulatableIntervention(BaseModel):
    """A retention action the trained model cannot represent.

    Recording these explicitly is a deliberate scientific choice: the honest
    answer to "what would a proactive support call do?" is that this model has no
    feature for it, so no estimate exists. Fabricating one would be worse than
    saying nothing.
    """

    model_config = ConfigDict(frozen=True)

    strategy_id: str
    intervention: str
    reason: str
    simulatable: Literal[False] = False
