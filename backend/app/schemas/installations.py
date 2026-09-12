"""Define anonymous installation request and response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class InstallationResponse(BaseModel):
    """Return anonymous installation credentials to the extension."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "installation_id": "7de98bb2-6523-4f1d-b09d-caa8c92dd8f0",
                "installation_token": "inst_0123456789abcdef",
                "owner_id": "18800e89-4b37-4355-9f65-dd48f2f2bb5c",
                "created_at": "2026-09-12T18:45:00Z",
            }
        }
    )

    installation_id: str
    installation_token: str
    owner_id: str
    created_at: datetime
