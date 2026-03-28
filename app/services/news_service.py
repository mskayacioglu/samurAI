from core import gather_news, normalize_filter_value


class NewsService:
    def gather(
        self,
        limit_per_source: int,
        language_key: str,
        selected_sources: list,
        topic_key: str = "",
        country_key: str = "",
        region_key: str = "",
    ):
        return gather_news(
            limit_per_source=limit_per_source,
            language_key=language_key,
            selected_sources=selected_sources,
            topic_key=topic_key,
            country_key=country_key,
            region_key=region_key,
        )

    def normalize_filter(self, value: str) -> str:
        return normalize_filter_value(value)
