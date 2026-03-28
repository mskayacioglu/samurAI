from core import clean_article_for_summarization, fetch_article_image, fetch_article_text


class ArticleService:
    def fetch_and_clean(self, item: dict, language_key: str) -> str:
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
        return item.get("image_url") or fetch_article_image(item["link"])
