from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, Literal, Dict, Any

Transport = Literal["bus", "train", "plane"]


DEFAULT_CONFIDENCE: Dict[str, float] = {
    "from": 1.0,
    "to": 1.0,
    "date": 1.0,
    "transport": 1.0,
}


class SlotsModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, validate_assignment=False)

    from_: Optional[str] = Field(None, alias="from")
    to: Optional[str] = None
    date: Optional[str] = None  # ISO YYYY-MM-DD
    transport: Optional[str] = None
    confidence: Dict[str, float] = Field(
        default_factory=lambda: DEFAULT_CONFIDENCE.copy()
    )

    @field_validator("confidence", mode="before")
    @classmethod
    def _sanitize_confidence(cls, v: Any) -> Dict[str, float]:
        base = DEFAULT_CONFIDENCE.copy()
        if isinstance(v, dict):
            for key in base:
                val = v.get(key)
                try:
                    base[key] = float(val)
                except (TypeError, ValueError):
                    base[key] = 0.0
        return base
