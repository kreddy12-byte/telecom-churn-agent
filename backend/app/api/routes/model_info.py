"""Public model-transparency endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.responses import MODEL_ERRORS
from app.core.auth import get_authenticated_user
from app.schemas.model_info import ModelInfoResponse
from app.services import model_info_service

router = APIRouter(tags=["model"], dependencies=[Depends(get_authenticated_user)])


@router.get(
    "/model",
    response_model=ModelInfoResponse,
    responses={503: MODEL_ERRORS[503]},
    summary="Trained model information",
    description=(
        "Safe subset of the locked training metadata: model name, version, "
        "dataset size, evaluation metrics, and explainability method. "
        "Filesystem paths and environment details are omitted."
    ),
)
def get_model_info() -> ModelInfoResponse:
    return model_info_service.get_model_info()
