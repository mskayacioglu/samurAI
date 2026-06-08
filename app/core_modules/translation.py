"""Optional multilingual translation model helpers."""

from .runtime import *
from .catalog import *
from .text_processing import *

def load_translator():
    """Load and cache the optional translation tokenizer and model."""
    model_ref = (TRANSLATION_MODEL_REF or "").strip()
    if not model_ref:
        return None, None, None
    if AutoTokenizer is None or AutoModelForSeq2SeqLM is None:
        raise RuntimeError("transformers and torch are required for translation.")

    local_only = os.path.isdir(model_ref)
    tokenizer = AutoTokenizer.from_pretrained(model_ref, local_files_only=local_only)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_ref, local_files_only=local_only)

    if torch is not None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = model.to(device)
        if device == "cpu":
            model = model.float()
    else:
        device = "cpu"
    model.eval()
    return tokenizer, model, device


def translate_text(text: str, source_language_key: str, target_language_key: str) -> str:
    """Translate text between supported languages when a model is configured."""
    text = normalize_text(text)
    if not text or source_language_key == target_language_key:
        return text

    source_lang_code = LANGUAGE_CONFIGS.get(source_language_key, {}).get("mbart_lang")
    target_lang_code = LANGUAGE_CONFIGS.get(target_language_key, {}).get("mbart_lang")
    if not source_lang_code or not target_lang_code:
        return text

    try:
        tokenizer, model, device = load_translator()
        if not tokenizer or not model:
            return text

        if hasattr(tokenizer, "src_lang"):
            tokenizer.src_lang = source_lang_code

        inputs = tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=768,
        )
        if torch is not None:
            inputs = {k: v.to(device) for k, v in inputs.items()}

        generate_kwargs = {
            "max_length": 280,
            "num_beams": 4,
            "no_repeat_ngram_size": 3,
            "repetition_penalty": 1.05,
            "early_stopping": True,
        }
        lang_code_to_id = getattr(tokenizer, "lang_code_to_id", {})
        if target_lang_code in lang_code_to_id:
            generate_kwargs["forced_bos_token_id"] = lang_code_to_id[target_lang_code]

        with torch.no_grad() if torch is not None else nullcontext():
            output_ids = model.generate(**inputs, **generate_kwargs)

        translated = tokenizer.decode(output_ids[0], skip_special_tokens=True).strip()
        translated = normalize_text(translated)
        return translated if translated else text
    except Exception:
        return text


__all__ = [name for name in globals() if not name.startswith("__")]
