"""
Museum Platform - Wikidata Adapter
Staged adapter for querying structured heritage entity graphs and external identifiers.
"""

from typing import Optional
from .base import BaseSourceAdapter
from ..models import SourceConfig


class WikidataAdapter(BaseSourceAdapter):
    def __init__(self, config: Optional[SourceConfig] = None):
        if not config:
            from ..source_registry import DEFAULT_SOURCES
            config = DEFAULT_SOURCES["WIKIDATA"]
        super().__init__(config)
