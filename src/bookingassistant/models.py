from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal, Dict

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
