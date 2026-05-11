from typing import Any, Optional
from pydantic import BaseModel

class ExternalCommandGate(BaseModel):
    """Gate that executes an external command and checks for success."""
    id: str
    name: str
    command: list[str]
    timeout_seconds: int = 30
    severity: str = "blocking"
    enabled: bool = True

class MetricThresholdGate(BaseModel):
    """Gate that parses a metric from a file and checks a threshold."""
    id: str
    name: str
    metric_file: str
    metric_key: str
    threshold: float
    operator: str = ">=" # >, <, >=, <=, ==
    severity: str = "blocking"
    enabled: bool = True
