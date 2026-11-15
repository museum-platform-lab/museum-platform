"""
Museum Platform - UNESCO Adapters (World Heritage & Intangible Cultural Heritage)
Staged source adapters for international heritage conventions and repositories.
"""

from typing import Optional
from .base import BaseSourceAdapter
from ..models import SourceConfig


class UNESCOWorldHeritageAdapter(BaseSourceAdapter):
    def __init__(self, config: Optional[SourceConfig] = None):
        if not config:
            from ..source_registry import DEFAULT_SOURCES
            config = DEFAULT_SOURCES["UNESCO_WH"]
        super().__init__(config)


class UNESCOIntangibleHeritageAdapter(BaseSourceAdapter):
    def __init__(self, config: Optional[SourceConfig] = None):
        if not config:
            from ..source_registry import DEFAULT_SOURCES
            config = DEFAULT_SOURCES["UNESCO_ICH"]
        super().__init__(config)
