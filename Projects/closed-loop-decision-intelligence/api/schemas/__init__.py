from pydantic import BaseModel, Field


class ApprovalInput(BaseModel):
    actor: str = Field(min_length=3, max_length=100)
    reason: str | None = Field(default=None, max_length=1000)


class StatusResponse(BaseModel):
    status: str
