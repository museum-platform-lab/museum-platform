"""
Museum Platform - DCH Adapter (Cục Di sản văn hóa)
Staged source adapter for the national heritage authority database (dsvh.gov.vn).
"""

from typing import Optional
from .base import BaseSourceAdapter
from ..models import SourceConfig


class DCHAdapter(BaseSourceAdapter):
    def __init__(self, config: Optional[SourceConfig] = None):
        if not config:
            from ..source_registry import DEFAULT_SOURCES
            config = DEFAULT_SOURCES["DCH"]
        super().__init__(config)
