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
    @property
    def sources(self):
        return NEWS_SOURCES

    @property
    def languages(self):
        return LANGUAGE_CONFIGS

    @property
    def topics(self):
        return TOPIC_CONFIGS

    @property
    def regions(self):
        return REGION_CONFIGS

    @property
    def countries(self):
        return COUNTRY_CONFIGS

    @property
    def models(self):
        return MODEL_PATHS

    @property
    def default_model(self):
        return DEFAULT_MODEL_KEY

    @property
    def default_language(self):
        return DEFAULT_LANGUAGE_KEY if DEFAULT_LANGUAGE_KEY in LANGUAGE_CONFIGS else "en"

    @property
    def translation_model_ref(self):
        return TRANSLATION_MODEL_REF

    def is_valid_language(self, key: str) -> bool:
        return key in LANGUAGE_CONFIGS

    def is_valid_model(self, key: str) -> bool:
        return key in MODEL_PATHS

    def available_language_keys(self):
        return list(LANGUAGE_CONFIGS.keys())

    def available_model_keys(self):
        return list(MODEL_PATHS.keys())
