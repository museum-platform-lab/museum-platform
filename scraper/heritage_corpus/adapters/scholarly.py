"""
Museum Platform - Scholarly Publications Adapter
Staged adapter for querying archaeological monographs, excavation reports, and research metadata.
"""

from typing import Optional
from .base import BaseSourceAdapter
from ..models import SourceConfig


class ScholarlyAdapter(BaseSourceAdapter):
    def __init__(self, config: Optional[SourceConfig] = None):
        if not config:
            from ..source_registry import DEFAULT_SOURCES
            config = DEFAULT_SOURCES["SCHOLARLY"]
        super().__init__(config)
