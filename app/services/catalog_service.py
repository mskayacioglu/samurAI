"""Catalog accessors for models, languages, sources, and filters."""

from core import (
    COUNTRY_CONFIGS,
    DEFAULT_LANGUAGE_KEY,
    DEFAULT_MODEL_KEY,
    LANGUAGE_CONFIGS,
    MODEL_PATHS,
    NEWS_SOURCES,
    REGION_CONFIGS,
    TOPIC_CONFIGS,
    TRANSLATION_MODEL_REF,
)


class CatalogService:
    """Expose read-only catalog configuration to controllers and services."""

    @property
    def sources(self):
        """Return all configured news sources keyed by source id."""
        return NEWS_SOURCES

    @property
    def languages(self):
        """Return supported language configuration keyed by language id."""
        return LANGUAGE_CONFIGS

    @property
    def topics(self):
        """Return supported topic filter configuration."""
        return TOPIC_CONFIGS

    @property
    def regions(self):
        """Return supported region filter configuration."""
        return REGION_CONFIGS

    @property
    def countries(self):
        """Return supported country filter configuration."""
        return COUNTRY_CONFIGS

    @property
    def models(self):
        """Return available summarization model paths keyed by model id."""
        return MODEL_PATHS

    @property
    def default_model(self):
        """Return the default summarization model key."""
        return DEFAULT_MODEL_KEY

    @property
    def default_language(self):
        """Return the default language key, falling back to English."""
        return DEFAULT_LANGUAGE_KEY if DEFAULT_LANGUAGE_KEY in LANGUAGE_CONFIGS else "en"

    @property
    def translation_model_ref(self):
        """Return the configured translation model reference or path."""
        return TRANSLATION_MODEL_REF

    def is_valid_language(self, key: str) -> bool:
        """Return whether a language key is supported."""
        return key in LANGUAGE_CONFIGS

    def is_valid_model(self, key: str) -> bool:
        """Return whether a model key is supported."""
        return key in MODEL_PATHS

    def available_language_keys(self):
        """Return all supported language keys."""
        return list(LANGUAGE_CONFIGS.keys())

    def available_model_keys(self):
        """Return all supported summarization model keys."""
        return list(MODEL_PATHS.keys())
