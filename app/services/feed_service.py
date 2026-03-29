from datetime import datetime, timezone

from services.catalog_service import CatalogService
from services.storage_service import StorageService
from services.translation_service import TranslationService


class FeedService:
    def __init__(
        self,
        catalog_service: CatalogService,
        storage_service: StorageService,
        translation_service: TranslationService,
    ):
        self.catalog_service = catalog_service
        self.storage_service = storage_service
        self.translation_service = translation_service

    def load_news(
        self,
        language_key: str,
        output_language: str,
        model_key: str,
        selected_sources: list[str],
        topic_key: str,
        country_key: str,
        region_key: str,
        limit_per_source: int,
        include_raw: bool,
        keyword: str = "",
    ):
        source_count = len(selected_sources)
        if source_count == 0:
            source_count = max(1, len([k for k, v in self.catalog_service.sources.items() if v.get("language") == language_key]))

        query_limit = max(20, min(1000, source_count * limit_per_source * 6))
        rows = self.storage_service.fetch_news_items_with_summary(
            language_key=language_key,
            model_key=model_key,
            topic_key=topic_key,
            country_key=country_key,
            region_key=region_key,
            selected_sources=selected_sources,
            keyword=keyword,
            limit=query_limit,
        )

        result = []
        produced_per_source = {}
        translation_applied_count = 0

        for row in rows:
            source_key = row["source_key"]
            source_count = produced_per_source.get(source_key, 0)
            if source_count >= limit_per_source:
                continue

            summary = row["summary"]
            if not summary:
                continue

            title_out, summary_out, translation_applied = self.translation_service.translate_if_needed(
                title=row["title"],
                summary=summary,
                source_language=language_key,
                target_language=output_language,
            )
            if translation_applied:
                translation_applied_count += 1

            result.append(
                {
                    "title": title_out,
                    "summary": summary_out,
                    "source_name": row["source_name"],
                    "source_key": source_key,
                    "link": row["link"],
                    "published_at": row["published_at"],
                    "image_url": row["image_url"],
                    "summary_input_type": "article",
                    "source_language": language_key,
                    "output_language": output_language,
                    "translation_applied": translation_applied,
                    "raw_text": row["article_text"] if include_raw else None,
                }
            )
            produced_per_source[source_key] = source_count + 1

        return {
            "items": result,
            "count": len(result),
            "translation_applied_count": translation_applied_count,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
