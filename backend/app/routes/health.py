"""Health check routes for the backend API."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Health check response.

    Attributes:
        status: Service health marker.
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]


@router.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    """Return a simple service health response.

    Returns:
        A successful health response.
    """

    return HealthResponse(status="ok")
