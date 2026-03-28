from controllers.news_controller import NewsController
from services.article_service import ArticleService
from services.catalog_service import CatalogService
from services.news_service import NewsService
from services.summarization_service import SummarizationService
from services.translation_service import TranslationService


class AppContainer:
    def __init__(self):
        self.catalog_service = CatalogService()
        self.news_service = NewsService()
        self.article_service = ArticleService()
        self.summarization_service = SummarizationService()
        self.translation_service = TranslationService()

    def build_news_controller(self) -> NewsController:
        return NewsController(
            catalog_service=self.catalog_service,
            news_service=self.news_service,
            article_service=self.article_service,
            summarization_service=self.summarization_service,
            translation_service=self.translation_service,
        )
