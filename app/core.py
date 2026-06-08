"""Compatibility exports for the split core modules."""

from core_modules import (
    article_extraction,
    catalog,
    filters,
    rss,
    runtime,
    summarization,
    text_processing,
    translation,
)

_MODULES = (
    runtime,
    catalog,
    text_processing,
    article_extraction,
    rss,
    summarization,
    translation,
    filters,
)

for _module in _MODULES:
    for _name, _value in vars(_module).items():
        if not _name.startswith("__"):
            globals()[_name] = _value

__all__ = [name for name in globals() if not name.startswith("_")]
