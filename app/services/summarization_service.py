from core import (
    extractive_fallback,
    normalize_text,
    postprocess_summary,
    summarize_article_cached,
)


class SummarizationService:
    def summarize_article(self, text: str, title: str, model_key: str, language_key: str, article_key: str) -> str:
        summary = summarize_article_cached(text, model_key, language_key, article_key=article_key)
        summary = postprocess_summary(summary, title, language_key)
        if summary:
            return summary
        return normalize_text(extractive_fallback(text, avoid_text=title))
