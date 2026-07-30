from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas import OverrideRequest


def test_valid_override() -> None:
    request = OverrideRequest(
        warehouse_code="WH-HAM",
        sku_code="ELEC-1001",
        override_type="DEMAND_MULTIPLIER",
        numeric_value=1.2,
        effective_from=datetime.now(timezone.utc),
        reason="Promotion expected",
        submitted_by="planner@example.com",
    )
    assert request.numeric_value == 1.2


def test_invalid_negative_count() -> None:
    with pytest.raises(ValidationError):
        OverrideRequest(
            warehouse_code="WH-HAM",
            sku_code="ELEC-1001",
            override_type="PHYSICAL_COUNT",
            numeric_value=-1,
            effective_from=datetime.now(timezone.utc),
            reason="Bad count",
            submitted_by="planner@example.com",
        )
