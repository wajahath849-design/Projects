"""Automated data-quality assessment and pipeline gating."""

from decision_intelligence.quality.data_quality import (
    DataQualityGateError,
    DataQualityReport,
    run_data_quality,
)

__all__ = ["DataQualityGateError", "DataQualityReport", "run_data_quality"]
