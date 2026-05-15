from pydantic import BaseModel, field_validator


DEFAULT_METRIC_THRESHOLDS: dict[str, dict[str, float | None]] = {
    "pe_ratio": {"min": None, "max": 20},
    "peg_ratio": {"min": None, "max": 1.5},
    "pb_ratio": {"min": None, "max": 3},
    "roe": {"min": 15, "max": None},
    "current_ratio": {"min": 1.5, "max": None},
    "debt_to_equity": {"min": None, "max": 1.0},
    "gross_margin": {"min": 30, "max": None},
    "dividend_yield": {"min": 1, "max": None},
}

DEFAULT_CATEGORY_WEIGHTS: dict[str, int] = {
    "value": 25,
    "growth": 25,
    "financial_health": 25,
    "profitability": 25,
}

VALID_RISK_TOLERANCES = {"conservative", "moderate", "aggressive"}
VALID_HOLD_DURATIONS = {"1-3y", "3-5y", "5y+"}


class PreferencesResponse(BaseModel):
    preferred_sectors: list[str]
    risk_tolerance: str
    hold_duration: str
    category_weights: dict[str, int]
    metric_overrides: dict[str, dict[str, float | None]]


class PreferencesUpdate(BaseModel):
    preferred_sectors: list[str] | None = None
    risk_tolerance: str | None = None
    hold_duration: str | None = None
    category_weights: dict[str, int] | None = None
    metric_overrides: dict[str, dict[str, float | None]] | None = None

    @field_validator("risk_tolerance")
    @classmethod
    def validate_risk_tolerance(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_RISK_TOLERANCES:
            raise ValueError(f"Must be one of: {', '.join(sorted(VALID_RISK_TOLERANCES))}")
        return v

    @field_validator("hold_duration")
    @classmethod
    def validate_hold_duration(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_HOLD_DURATIONS:
            raise ValueError(f"Must be one of: {', '.join(sorted(VALID_HOLD_DURATIONS))}")
        return v

    @field_validator("category_weights")
    @classmethod
    def validate_category_weights(cls, v: dict[str, int] | None) -> dict[str, int] | None:
        if v is None:
            return v
        valid_keys = {"value", "growth", "financial_health", "profitability"}
        if set(v.keys()) != valid_keys:
            raise ValueError(f"Must contain exactly these keys: {', '.join(sorted(valid_keys))}")
        for key, weight in v.items():
            if not (0 <= weight <= 100):
                raise ValueError(f"Weight for '{key}' must be between 0 and 100")
        return v
