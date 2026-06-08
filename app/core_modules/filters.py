"""Source filtering and multi-source news aggregation."""

from .runtime import *
from .catalog import *
from .text_processing import normalize_text
from .rss import fetch_source_news

def normalize_filter_value(value: str) -> str:
    """Normalize filter values and map all-like inputs to an empty filter."""
    normalized = normalize_text(value).lower()
    if normalized in {"", "__all__", "all"}:
        return ""
    return normalized


def filter_sources(
    language_key: str,
    topic_key: str = "",
    country_key: str = "",
    region_key: str = "",
):
    """Return news sources that match language, topic, country, and region."""
    topic_key = normalize_filter_value(topic_key)
    country_key = normalize_filter_value(country_key).upper()
    region_key = normalize_filter_value(region_key)
    filtered = {}
    for key, source in NEWS_SOURCES.items():
        if source.get("language") != language_key:
            continue
        if topic_key and source.get("topic") != topic_key:
            continue
        if country_key and (source.get("country") or "").upper() != country_key:
            continue
        if region_key and source.get("region") != region_key:
            continue
        filtered[key] = source
    return filtered


def gather_news(
    limit_per_source: int,
    language_key: str,
    selected_sources: list,
    topic_key: str = "",
    country_key: str = "",
    region_key: str = "",
):
    """Gather and sort news entries across selected sources for a language."""
    lang_sources = filter_sources(
        language_key=language_key,
        topic_key=topic_key,
        country_key=country_key,
        region_key=region_key,
    )
    if selected_sources:
        keys = [k for k in selected_sources if k in lang_sources]
        if not keys:
            return []
    else:
        keys = list(lang_sources.keys())

    all_entries = []

    raw_limit = max(1, limit_per_source * max(1, SOURCE_OVERSAMPLE_FACTOR))
    for key in keys:
        cfg = lang_sources[key]
        all_entries.extend(fetch_source_news(key, cfg, raw_limit))

    all_entries.sort(
        key=lambda x: x["published_at"] or datetime.fromtimestamp(0, tz=timezone.utc),
        reverse=True,
    )
    return all_entries

__all__ = [name for name in globals() if not name.startswith("__")]
