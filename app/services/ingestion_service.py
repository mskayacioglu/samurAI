import os
import re
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

from core import LANGUAGE_CONFIGS
from services.article_service import ArticleService
from services.catalog_service import CatalogService
from services.news_service import NewsService
from services.summarization_service import SummarizationService
from services.storage_service import StorageService


TRUTHY = {"1", "true", "yes", "on"}


class IngestionService:
    def __init__(
        self,
        catalog_service: CatalogService,
        news_service: NewsService,
        article_service: ArticleService,
        summarization_service: SummarizationService,
        storage_service: StorageService,
    ):
        self.catalog_service = catalog_service
        self.news_service = news_service
        self.article_service = article_service
        self.summarization_service = summarization_service
        self.storage_service = storage_service

    @staticmethod
    def _parse_iso_datetime(value: str) -> datetime | None:
        text = (value or "").strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _default_model_keys() -> list[str]:
        # Precompute both multilingual models by default.
        return ["mbart50_xlsum", "mt5-xlsum"]

    def _resolve_model_keys(self) -> list[str]:
        raw_model_keys = (os.getenv("INGEST_MODEL_KEYS") or "").strip()
        if raw_model_keys:
            candidates = [key.strip() for key in raw_model_keys.split(",") if key.strip()]
        else:
            candidates = self._default_model_keys()

        valid = []
        for key in candidates:
            if self.catalog_service.is_valid_model(key) and key not in valid:
                valid.append(key)
        if valid:
            return valid
        return [self.catalog_service.default_model]

    @staticmethod
    def _build_language_budgets(languages: list[str], total_budget: int) -> dict[str, int]:
        if not languages:
            return {}
        total_budget = max(1, int(total_budget))
        count = len(languages)

        budgets = {lang: 0 for lang in languages}
        if total_budget < count:
            for lang in languages[:total_budget]:
                budgets[lang] = 1
            return budgets

        base = total_budget // count
        remainder = total_budget % count
        for idx, lang in enumerate(languages):
            budgets[lang] = base + (1 if idx < remainder else 0)
        return budgets

    @staticmethod
    def _round_robin_entries_by_source(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, deque] = defaultdict(deque)
        source_order: list[str] = []

        for entry in entries:
            source_key = entry.get("source_key", "")
            if source_key not in grouped:
                source_order.append(source_key)
            grouped[source_key].append(entry)

        result: list[dict[str, Any]] = []
        while source_order:
            remaining_sources: list[str] = []
            for source_key in source_order:
                bucket = grouped.get(source_key)
                if not bucket:
                    continue
                result.append(bucket.popleft())
                if bucket:
                    remaining_sources.append(source_key)
            source_order = remaining_sources
        return result

    def load_runtime_config(self) -> dict[str, Any]:
        raw_languages = (os.getenv("INGEST_LANGUAGES") or "").strip()
        if raw_languages:
            languages = [lang.strip().lower() for lang in raw_languages.split(",") if lang.strip()]
        else:
            languages = list(LANGUAGE_CONFIGS.keys())

        valid_languages = [lang for lang in languages if self.catalog_service.is_valid_language(lang)]
        if not valid_languages:
            valid_languages = list(LANGUAGE_CONFIGS.keys())

        raw_sources = (os.getenv("INGEST_SOURCES") or "").strip()
        selected_sources = [src.strip() for src in raw_sources.split(",") if src.strip()]
        from_datetime = self._parse_iso_datetime(os.getenv("INGEST_FROM_DATE", ""))
        until_datetime = self._parse_iso_datetime(os.getenv("INGEST_UNTIL_DATE", ""))
        limit_per_source = max(1, min(int(os.getenv("INGEST_LIMIT_PER_SOURCE", "50")), 500))
        fetch_limit_per_source = max(
            limit_per_source,
            min(int(os.getenv("INGEST_FETCH_LIMIT_PER_SOURCE", "50")), 500),
        )

        return {
            "model_keys": self._resolve_model_keys(),
            "languages": valid_languages,
            "limit_per_source": limit_per_source,
            "fetch_limit_per_source": fetch_limit_per_source,
            "topic": self.news_service.normalize_filter(os.getenv("INGEST_TOPIC", "")),
            "country": self.news_service.normalize_filter(os.getenv("INGEST_COUNTRY", "")).upper(),
            "region": self.news_service.normalize_filter(os.getenv("INGEST_REGION", "")),
            "selected_sources": selected_sources,
            "max_items_per_run": max(1, int(os.getenv("INGEST_MAX_ITEMS_PER_RUN", "200"))),
            "from_date": from_datetime.isoformat() if from_datetime else "",
            "until_date": until_datetime.isoformat() if until_datetime else "",
        }

    def _build_item_payload(self, source_item: dict[str, Any], language_key: str, article_text: str) -> dict[str, Any]:
        published_at = source_item.get("published_at")
        if published_at and not isinstance(published_at, datetime):
            published_at = None

        source_cfg = self.catalog_service.sources.get(source_item["source_key"], {})

        return {
            "link": source_item["link"],
            "source_key": source_item["source_key"],
            "source_name": source_item["source_name"],
            "language_key": language_key,
            "topic_key": source_cfg.get("topic", "general"),
            "country_key": source_cfg.get("country", ""),
            "region_key": source_cfg.get("region", "global"),
            "title": source_item["title"],
            "published_at": published_at.isoformat() if published_at else None,
            "image_url": self.article_service.resolve_image_url(source_item),
            "article_text": article_text,
        }

    def run_once(self, logger=None) -> dict[str, Any]:
        config = self.load_runtime_config()
        run_id = self.storage_service.start_ingest_run(config)
        from_date = self._parse_iso_datetime(config.get("from_date", ""))
        until_date = self._parse_iso_datetime(config.get("until_date", ""))
        language_budgets = self._build_language_budgets(
            config["languages"],
            config["max_items_per_run"],
        )
        stats = {
            "processed_entries": 0,
            "saved_items": 0,
            "summaries_written": 0,
            "skipped_no_article": 0,
            "skipped_no_summary": 0,
            "skipped_out_of_range": 0,
            "language_budgets": language_budgets,
            "language_breakdown": {},
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            for language_key in config["languages"]:
                language_budget = language_budgets.get(language_key, 0)
                lang_processed = 0
                gathered_entries = self.news_service.gather(
                    limit_per_source=config["fetch_limit_per_source"],
                    language_key=language_key,
                    selected_sources=config["selected_sources"],
                    topic_key=config["topic"],
                    country_key=config["country"],
                    region_key=config["region"],
                )
                entries = self._round_robin_entries_by_source(gathered_entries)

                produced_per_source: dict[str, int] = {}
                lang_stats = {
                    "entries_seen": 0,
                    "items_saved": 0,
                    "summaries": 0,
                    "skipped_no_article": 0,
                }

                for entry in entries:
                    if language_budget <= 0:
                        break
                    if lang_processed >= language_budget:
                        break
                    if stats["processed_entries"] >= config["max_items_per_run"]:
                        break

                    source_key = entry["source_key"]
                    current_count = produced_per_source.get(source_key, 0)
                    if current_count >= config["limit_per_source"]:
                        continue

                    published_at = entry.get("published_at")
                    if published_at and published_at.tzinfo is None:
                        published_at = published_at.replace(tzinfo=timezone.utc)
                    if from_date and published_at and published_at < from_date:
                        stats["skipped_out_of_range"] += 1
                        continue
                    if until_date and published_at and published_at > until_date:
                        stats["skipped_out_of_range"] += 1
                        continue

                    lang_stats["entries_seen"] += 1
                    stats["processed_entries"] += 1
                    lang_processed += 1

                    article_text = self.article_service.fetch_and_clean(entry, language_key)
                    if not article_text:
                        stats["skipped_no_article"] += 1
                        lang_stats["skipped_no_article"] += 1
                        continue

                    payload = self._build_item_payload(entry, language_key, article_text)
                    news_item_id, inserted = self.storage_service.upsert_news_item(payload)

                    created_summary_count = 0
                    for model_key in config["model_keys"]:
                        summary = self.summarization_service.summarize_article(
                            text=article_text,
                            title=entry["title"],
                            model_key=model_key,
                            language_key=language_key,
                            article_key=entry.get("link", ""),
                        )
                        summary = re.sub(r"\s+", " ", summary or "").strip()
                        if not summary:
                            continue
                        self.storage_service.upsert_summary(
                            news_item_id=news_item_id,
                            model_key=model_key,
                            language_key=language_key,
                            summary=summary,
                        )
                        created_summary_count += 1

                    if inserted:
                        stats["saved_items"] += 1
                        lang_stats["items_saved"] += 1
                    if created_summary_count == 0:
                        stats["skipped_no_summary"] += 1
                        continue
                    stats["summaries_written"] += created_summary_count
                    lang_stats["summaries"] += created_summary_count
                    produced_per_source[source_key] = current_count + 1

                    if logger is not None:
                        logger.info(
                            "ingest_saved source=%s language=%s models=%s title=%s",
                            entry["source_name"],
                            language_key,
                            ",".join(config["model_keys"]),
                            entry["title"][:100],
                        )

                stats["language_breakdown"][language_key] = lang_stats

            stats["finished_at"] = datetime.now(timezone.utc).isoformat()
            stats["run_capped"] = stats["processed_entries"] >= config["max_items_per_run"]
            self.storage_service.finish_ingest_run(run_id, "success", stats)
            return stats
        except Exception as exc:
            stats["finished_at"] = datetime.now(timezone.utc).isoformat()
            stats["error"] = str(exc)
            stats["run_capped"] = False
            self.storage_service.finish_ingest_run(run_id, "failed", stats, error_message=str(exc)[:800])
            raise

    def latest_status(self) -> dict[str, Any]:
        return self.storage_service.get_latest_ingest_run()

    @staticmethod
    def is_enabled() -> bool:
        return str(os.getenv("INGEST_ENABLED", "1")).strip().lower() in TRUTHY

    @staticmethod
    def run_on_start() -> bool:
        return str(os.getenv("INGEST_RUN_ON_START", "1")).strip().lower() in TRUTHY

    @staticmethod
    def interval_seconds() -> int:
        return max(60, int(os.getenv("INGEST_INTERVAL_SECONDS", "900")))
