"""
Museum Platform - Wikimedia Commons Media Adapter (Staged)
Staged source adapter for media metadata and licensing provenance.
"""

from typing import Optional
from .base import BaseSourceAdapter
from ..models import SourceConfig


class CommonsAdapter(BaseSourceAdapter):
    def __init__(self, config: Optional[SourceConfig] = None):
        if not config:
            from ..source_registry import DEFAULT_SOURCES
            config = DEFAULT_SOURCES["COMMONS"]
        super().__init__(config)
