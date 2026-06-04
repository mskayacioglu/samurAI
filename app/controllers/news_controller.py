"""HTTP controller methods for the news feed and ingest endpoints."""

from flask import jsonify, render_template, request

from core import normalize_filter_value
from services.catalog_service import CatalogService
from services.feed_service import FeedService
from services.ingestion_service import IngestionService
from services.ingest_scheduler_service import IngestSchedulerService


MULTILINGUAL_MODEL_KEYS = {"mbart50_xlsum", "mbart-xlsum-2", "mt5-xlsum"}


class NewsController:
    """Handle page rendering and JSON responses for news-related routes."""

    def __init__(
        self,
        catalog_service: CatalogService,
        feed_service: FeedService,
        ingestion_service: IngestionService,
        ingest_scheduler_service: IngestSchedulerService,
    ):
        self.catalog_service = catalog_service
        self.feed_service = feed_service
        self.ingestion_service = ingestion_service
        self.ingest_scheduler_service = ingest_scheduler_service

    def index(self):
        """Render the main news feed page with catalog and default settings."""
        ingest_model_keys = self.ingestion_service.load_runtime_config().get("model_keys", [])
        models = {
            key: value
            for key, value in self.catalog_service.models.items()
            if not ingest_model_keys or key in ingest_model_keys
        }
        default_model = self.catalog_service.default_model
        if default_model not in models and models:
            default_model = next(iter(models.keys()))

        return render_template(
            "index.html",
            sources=self.catalog_service.sources,
            languages=self.catalog_service.languages,
            topics=self.catalog_service.topics,
            countries=self.catalog_service.countries,
            regions=self.catalog_service.regions,
            models=models,
            default_model=default_model,
            default_language=self.catalog_service.default_language,
        )

    def api_news(self):
        """Return filtered news summaries and catalog metadata as JSON."""
        limit = int(request.args.get("limit", 2))
        source = request.args.get("source", "")
        language = request.args.get("language", self.catalog_service.default_language)
        output_language = request.args.get("output_language", language)
        model_key = request.args.get("model", self.catalog_service.default_model)
        sources_param = request.args.get("sources", "")
        topic = request.args.get("topic", "")
        country = request.args.get("country", "")
        region = request.args.get("region", "")
        include_raw = request.args.get("include_raw", "false").lower() == "true"
        keyword_enabled = request.args.get("keyword_enabled", "false").lower() == "true"
        keyword = request.args.get("keyword", "").strip()
        translation_model_active = bool((self.catalog_service.translation_model_ref or "").strip())
        ingest_model_keys = self.ingestion_service.load_runtime_config().get("model_keys", [])

        if not self.catalog_service.is_valid_language(language):
            return jsonify({"error": "Invalid language key", "languages": self.catalog_service.available_language_keys()}), 400

        if not self.catalog_service.is_valid_language(output_language):
            return jsonify({"error": "Invalid output language key", "languages": self.catalog_service.available_language_keys()}), 400

        available_models = [m for m in ingest_model_keys if self.catalog_service.is_valid_model(m)]
        if not available_models:
            available_models = self.catalog_service.available_model_keys()
        if language != "en":
            available_models = [m for m in available_models if m in MULTILINGUAL_MODEL_KEYS]

        if not self.catalog_service.is_valid_model(model_key) or model_key not in available_models:
            return jsonify({"error": "Invalid model key", "models": available_models}), 400

        if language != "en" and model_key not in MULTILINGUAL_MODEL_KEYS:
            model_key = "mbart50_xlsum"

        selected_sources = []
        if sources_param.strip():
            selected_sources = [s.strip() for s in sources_param.split(",") if s.strip()]
        elif source.strip():
            selected_sources = [source.strip()]

        limit_per_source = max(1, min(limit, 15))
        topic = normalize_filter_value(topic)
        country = normalize_filter_value(country).upper()
        region = normalize_filter_value(region)
        if keyword_enabled:
            if not keyword:
                return jsonify({"error": "Keyword is required when keyword search is enabled"}), 400
            if any(ch.isspace() for ch in keyword):
                return jsonify({"error": "Keyword must be a single word without spaces"}), 400
        else:
            keyword = ""

        news_payload = self.feed_service.load_news(
            language_key=language,
            output_language=output_language,
            model_key=model_key,
            selected_sources=selected_sources,
            topic_key=topic,
            country_key=country,
            region_key=region,
            limit_per_source=limit_per_source,
            include_raw=include_raw,
            keyword=keyword,
        )

        return jsonify(
            {
                "count": news_payload["count"],
                "model": model_key,
                "language": language,
                "output_language": output_language,
                "translation_model": self.catalog_service.translation_model_ref if translation_model_active else None,
                "topic": topic,
                "country": country,
                "region": region,
                "keyword": keyword,
                "available_models": available_models,
                "available_sources": self.catalog_service.sources,
                "available_languages": self.catalog_service.languages,
                "available_topics": self.catalog_service.topics,
                "available_regions": self.catalog_service.regions,
                "available_countries": self.catalog_service.countries,
                "items": news_payload["items"],
                "generated_at": news_payload["generated_at"],
            }
        )

    def api_ingest_status(self):
        """Return scheduler state and the latest ingest run status as JSON."""
        return jsonify(
            {
                "scheduler": self.ingest_scheduler_service.state(),
                "latest_run": self.ingestion_service.latest_status(),
            }
        )

    def api_ingest_trigger(self):
        """Queue an immediate ingest run when the scheduler is enabled."""
        if not self.ingestion_service.is_enabled():
            return jsonify({"error": "Ingest scheduler is disabled. Set INGEST_ENABLED=1."}), 400

        self.ingest_scheduler_service.trigger_now()
        return jsonify({"status": "queued"}), 202
