"""Article retrieval and cleanup service."""

from core import clean_article_for_summarization, fetch_article_image, fetch_article_text


class ArticleService:
    """Fetch article content and media metadata for RSS entries."""

    def fetch_and_clean(self, item: dict, language_key: str) -> str:
        """Fetch an article URL and return text cleaned for summarization."""
        article_text = fetch_article_text(item["link"], source_key=item.get("source_key", ""))
        if not article_text:
            return ""
        return clean_article_for_summarization(
            article_text,
            language_key,
            title=item["title"],
            source_key=item.get("source_key", ""),
            source_url=item.get("link", ""),
        )

    def resolve_image_url(self, item: dict) -> str:
        """Return the RSS image URL or fetch one from the article page."""
        return item.get("image_url") or fetch_article_image(item["link"])
