"""External data sources → ``RawItem``."""

from app.sources.arxiv_source import ArxivSource
from app.sources.base import BaseSource
from app.sources.company_site_source import CompanySiteSource
from app.sources.event_source import EventSource
from app.sources.github_source import GitHubSource
from app.sources.openalex_source import OpenAlexSource
from app.sources.rss_source import RSSSource

__all__ = [
    "BaseSource",
    "ArxivSource",
    "RSSSource",
    "GitHubSource",
    "OpenAlexSource",
    "EventSource",
    "CompanySiteSource",
]
