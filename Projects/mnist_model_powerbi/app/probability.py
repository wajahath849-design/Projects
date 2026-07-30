from __future__ import annotations

import numpy as np


def normalise_probabilities(values, expected_count: int) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64).reshape(-1)
    if array.size != expected_count or not np.all(np.isfinite(array)):
        raise ValueError(
            f"Expected {expected_count} finite outputs, received shape {array.shape}"
        )
    if (
        np.any(array < 0)
        or np.any(array > 1)
        or not np.isclose(array.sum(), 1.0, atol=1e-3)
    ):
        shifted = array - np.max(array)
        exponentials = np.exp(shifted)
        array = exponentials / exponentials.sum()
    if (
        np.any(array < 0)
        or np.any(array > 1)
        or not np.isclose(array.sum(), 1.0, atol=1e-5)
    ):
        raise ValueError(
            "The model output could not be converted into valid probabilities"
        )
    return array
