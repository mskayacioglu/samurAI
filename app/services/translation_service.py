from core import translate_text


class TranslationService:
    def translate_if_needed(self, title: str, summary: str, source_language: str, target_language: str):
        if target_language == source_language:
            return title, summary, False

        translated_title = translate_text(title, source_language, target_language)
        translated_summary = translate_text(summary, source_language, target_language)
        changed = bool(translated_title != title or translated_summary != summary)
        return translated_title, translated_summary, changed
