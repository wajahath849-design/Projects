from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


OverrideType = Literal[
    "PHYSICAL_COUNT",
    "DEMAND_MULTIPLIER",
    "LEAD_TIME_PENALTY",
    "SAFETY_STOCK",
    "REORDER_QTY",
    "HOLD_REPLENISHMENT",
]


class OverrideRequest(BaseModel):
    warehouse_code: str = Field(min_length=2, max_length=40, pattern=r"^[A-Z0-9][A-Z0-9_-]*$")
    sku_code: str = Field(min_length=3, max_length=80, pattern=r"^[A-Z0-9][A-Z0-9_-]*$")
    override_type: OverrideType
    numeric_value: float | None = None
    text_value: str | None = Field(default=None, max_length=500)
    effective_from: datetime
    effective_to: datetime | None = None
    reason: str = Field(min_length=5, max_length=500)
    submitted_by: str = Field(min_length=2, max_length=160)

    @model_validator(mode="after")
    def validate_values(self) -> "OverrideRequest":
        if self.numeric_value is None and not self.text_value:
            raise ValueError("Either numeric_value or text_value must be supplied")
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError("effective_to must be later than effective_from")
        if self.override_type in {"PHYSICAL_COUNT", "SAFETY_STOCK", "REORDER_QTY"}:
            if self.numeric_value is None or self.numeric_value < 0:
                raise ValueError(f"{self.override_type} requires a non-negative numeric_value")
        if self.override_type == "DEMAND_MULTIPLIER":
            if self.numeric_value is None or not 0 <= self.numeric_value <= 10:
                raise ValueError("DEMAND_MULTIPLIER must be between 0 and 10")
        if self.override_type == "LEAD_TIME_PENALTY":
            if self.numeric_value is None or not 0 <= self.numeric_value <= 365:
                raise ValueError("LEAD_TIME_PENALTY must be between 0 and 365 days")
        return self


class JobRequest(BaseModel):
    job_type: Literal["FULL_PIPELINE", "FORECAST", "REPLENISHMENT", "INGEST_CSV", "OVERRIDE_RECALC", "INGEST_DOCUMENT", "INGEST_EXTERNAL_SIGNAL"]
    payload: dict[str, Any] = Field(default_factory=dict)
    requested_by: str = Field(min_length=2, max_length=160)
    priority: int = Field(default=100, ge=1, le=1000)


class JobResponse(BaseModel):
    job_id: UUID
    status: str


class CsvIngestionRequest(BaseModel):
    file_path: str = Field(min_length=1, max_length=1000)
    dataset_type: Literal["transactions", "snapshots", "lead_times"]
    requested_by: str = Field(min_length=2, max_length=160)


class PipelineRunResult(BaseModel):
    model_run_id: int
    forecast_rows: int
    recommendation_rows: int
    started_at: datetime
    finished_at: datetime
    warnings: list[str] = Field(default_factory=list)


class OverrideApprovalRequest(BaseModel):
    approved_by: str = Field(min_length=2, max_length=160)
    approve: bool = True
