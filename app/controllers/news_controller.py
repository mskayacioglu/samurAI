from datetime import datetime, timezone

from flask import jsonify, render_template, request

from services.article_service import ArticleService
from services.catalog_service import CatalogService
from services.news_service import NewsService
from services.summarization_service import SummarizationService
from services.translation_service import TranslationService


class NewsController:
    def __init__(
        self,
        catalog_service: CatalogService,
        news_service: NewsService,
        article_service: ArticleService,
        summarization_service: SummarizationService,
        translation_service: TranslationService,
    ):
        self.catalog_service = catalog_service
        self.news_service = news_service
        self.article_service = article_service
        self.summarization_service = summarization_service
        self.translation_service = translation_service

    def index(self):
        return render_template(
            "index.html",
            sources=self.catalog_service.sources,
            languages=self.catalog_service.languages,
            topics=self.catalog_service.topics,
            countries=self.catalog_service.countries,
            regions=self.catalog_service.regions,
            models=self.catalog_service.models,
            default_model=self.catalog_service.default_model,
            default_language=self.catalog_service.default_language,
        )

    def api_news(self, app):
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
        translation_model_active = bool((self.catalog_service.translation_model_ref or "").strip())

        if not self.catalog_service.is_valid_language(language):
            return jsonify({"error": "Invalid language key", "languages": self.catalog_service.available_language_keys()}), 400

        if not self.catalog_service.is_valid_language(output_language):
            return jsonify({"error": "Invalid output language key", "languages": self.catalog_service.available_language_keys()}), 400

        if not self.catalog_service.is_valid_model(model_key):
            return jsonify({"error": "Invalid model key", "models": self.catalog_service.available_model_keys()}), 400

        if language != "en" and model_key != "mbart50_xlsum":
            model_key = "mbart50_xlsum"

        selected_sources = []
        if sources_param.strip():
            selected_sources = [s.strip() for s in sources_param.split(",") if s.strip()]
        elif source.strip():
            selected_sources = [source.strip()]

        limit_per_source = max(1, min(limit, 15))
        entries = self.news_service.gather(
            limit_per_source=limit_per_source,
            language_key=language,
            selected_sources=selected_sources,
            topic_key=topic,
            country_key=country,
            region_key=region,
        )

        result = []
        source_type_counts = {"article": 0, "rss": 0}
        skipped_due_to_missing_article = 0
        produced_per_source = {}

        for item in entries:
            source_key = item["source_key"]
            current_count = produced_per_source.get(source_key, 0)
            if current_count >= limit_per_source:
                continue

            article_text = self.article_service.fetch_and_clean(item, language)
            if not article_text:
                skipped_due_to_missing_article += 1
                app.logger.info("article_fetch_skip source=%s link=%s", item["source_name"], item["link"][:180])
                continue

            summary = self.summarization_service.summarize_article(
                text=article_text,
                title=item["title"],
                model_key=model_key,
                language_key=language,
                article_key=item.get("link", ""),
            )

            title_out, summary_out, translation_applied = self.translation_service.translate_if_needed(
                title=item["title"],
                summary=summary,
                source_language=language,
                target_language=output_language,
            )

            image_url = self.article_service.resolve_image_url(item)
            source_type_counts["article"] = source_type_counts.get("article", 0) + 1
            produced_per_source[source_key] = current_count + 1

            app.logger.info(
                "summary_input_type=%s source=%s title=%s",
                "article",
                item["source_name"],
                item["title"][:100],
            )

            result.append(
                {
                    "title": title_out,
                    "summary": summary_out,
                    "source_name": item["source_name"],
                    "source_key": item["source_key"],
                    "link": item["link"],
                    "published_at": item["published_at"].isoformat() if item["published_at"] else None,
                    "image_url": image_url,
                    "summary_input_type": "article",
                    "source_language": language,
                    "output_language": output_language,
                    "translation_applied": translation_applied,
                    "raw_text": article_text if include_raw else None,
                }
            )

        app.logger.info(
            "request_done language=%s output_language=%s model=%s translation_model=%s items=%s article_based=%s rss_based=%s skipped_no_article=%s",
            language,
            output_language,
            model_key,
            self.catalog_service.translation_model_ref if translation_model_active else "disabled",
            len(result),
            source_type_counts.get("article", 0),
            source_type_counts.get("rss", 0),
            skipped_due_to_missing_article,
        )

        return jsonify(
            {
                "count": len(result),
                "model": model_key,
                "language": language,
                "output_language": output_language,
                "translation_model": self.catalog_service.translation_model_ref if translation_model_active else None,
                "topic": self.news_service.normalize_filter(topic),
                "country": self.news_service.normalize_filter(country).upper(),
                "region": self.news_service.normalize_filter(region),
                "available_models": self.catalog_service.available_model_keys(),
                "available_sources": self.catalog_service.sources,
                "available_languages": self.catalog_service.languages,
                "available_topics": self.catalog_service.topics,
                "available_regions": self.catalog_service.regions,
                "available_countries": self.catalog_service.countries,
                "items": result,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
