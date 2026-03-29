from controllers.news_controller import NewsController
from services.article_service import ArticleService
from services.catalog_service import CatalogService
from services.feed_service import FeedService
from services.ingest_scheduler_service import IngestSchedulerService
from services.ingestion_service import IngestionService
from services.news_service import NewsService
from services.storage_service import StorageService
from services.summarization_service import SummarizationService
from services.translation_service import TranslationService


class AppContainer:
    def __init__(self):
        self.catalog_service = CatalogService()
        self.news_service = NewsService()
        self.article_service = ArticleService()
        self.summarization_service = SummarizationService()
        self.translation_service = TranslationService()
        self.storage_service = StorageService()
        self.ingestion_service = IngestionService(
            catalog_service=self.catalog_service,
            news_service=self.news_service,
            article_service=self.article_service,
            summarization_service=self.summarization_service,
            storage_service=self.storage_service,
        )
        self.feed_service = FeedService(
            catalog_service=self.catalog_service,
            storage_service=self.storage_service,
            translation_service=self.translation_service,
        )
        self.ingest_scheduler_service = IngestSchedulerService(self.ingestion_service)

    def build_news_controller(self) -> NewsController:
        return NewsController(
            catalog_service=self.catalog_service,
            feed_service=self.feed_service,
            ingestion_service=self.ingestion_service,
            ingest_scheduler_service=self.ingest_scheduler_service,
        )

    def start_background_jobs(self, logger=None):
        if logger is not None:
            self.ingest_scheduler_service.logger = logger

        if self.ingestion_service.is_enabled():
            self.ingest_scheduler_service.start()
            if logger is not None:
                logger.info(
                    "ingest_scheduler_started interval_seconds=%s",
                    self.ingestion_service.interval_seconds(),
                )

    def shutdown(self):
        self.ingest_scheduler_service.stop()
