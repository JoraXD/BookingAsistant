from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal

Transport = Literal['bus', 'train', 'plane']


class SlotsModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, validate_assignment=False)

    from_: Optional[str] = Field(None, alias='from')
    to: Optional[str] = None
    date: Optional[str] = None  # ISO YYYY-MM-DD
    transport: Optional[Transport] = None
    confidence: Optional[float] = 1.0
