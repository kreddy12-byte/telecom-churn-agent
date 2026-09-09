"""What-if simulation endpoint.

The backend resolves the customer and the requested scenarios, then hands them
to the locked Step 5 engine. No probability, SHAP value, or ranking score is
computed here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.responses import SIMULATION_ERRORS
from app.core.auth import get_authenticated_user
from app.core.dependencies import ProviderDep, SessionDep
from app.schemas.whatif import WhatIfRequest, WhatIfResponse
from app.services import whatif_service

router = APIRouter(tags=["what-if"], dependencies=[Depends(get_authenticated_user)])


@router.post(
    "/what-if",
    response_model=WhatIfResponse,
    status_code=status.HTTP_200_OK,
    responses=SIMULATION_ERRORS,
    summary="Compare hypothetical retention scenarios",
    description=(
        "Evaluates how the **existing** trained model responds to hypothetical "
        "customer-profile changes. Results are model-based what-if estimates, "
        "not causal predictions: every payload includes the disclaimer "
        "'Model-based what-if estimate — not a causal prediction.' "
        "`requires_human_approval` is always true. The simulator changes no "
        "customer record and performs no real-world action."
    ),
)
def run_whatif(
    request: WhatIfRequest,
    session: SessionDep,
    provider: ProviderDep,
) -> WhatIfResponse:
    return whatif_service.simulate_for_customer(session, request, provider=provider)
