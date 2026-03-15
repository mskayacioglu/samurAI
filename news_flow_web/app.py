import os
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from functools import lru_cache
from urllib.error import URLError
from urllib.request import urlopen
from xml.etree import ElementTree as ET

from flask import Flask, jsonify, render_template, request

try:
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
except ImportError:
    torch = None
    AutoModelForSeq2SeqLM = None
    AutoTokenizer = None


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))

MODEL_PATHS = {
    "bart_large_cnn": os.path.join(PROJECT_ROOT, "models", "bart_large-cnn"),
    "bart_base_cnn": os.path.join(PROJECT_ROOT, "models", "bart_base-cnn"),
    "bart_reuters": os.path.join(
        PROJECT_ROOT, "models", "bart_base-reuters", "bart-reuters-best"
    ),
}

DEFAULT_MODEL_KEY = os.getenv("MODEL_KEY", "bart_large_cnn")
MAX_INPUT_CHARS = int(os.getenv("MAX_INPUT_CHARS", "3500"))
DEFAULT_SUMMARY_TOKENS = int(os.getenv("SUMMARY_MAX_TOKENS", "96"))

NEWS_SOURCES = {
    "bbc_world": {
        "name": "BBC World",
        "rss_url": "https://feeds.bbci.co.uk/news/world/rss.xml",
    },
    "guardian_world": {
        "name": "The Guardian World",
        "rss_url": "https://www.theguardian.com/world/rss",
    },
    "aljazeera_all": {
        "name": "Al Jazeera",
        "rss_url": "https://www.aljazeera.com/xml/rss/all.xml",
    },
}


def strip_html(text: str) -> str:
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", clean).strip()


def extractive_fallback(text: str, max_chars: int = 280) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", text)
    picked = " ".join(parts[:2]).strip() if parts else text
    if len(picked) <= max_chars:
        return picked
    return picked[:max_chars].rsplit(" ", 1)[0] + "..."


def is_degenerate_summary(summary: str) -> bool:
    tokens = re.findall(r"\b[\w'-]+\b", (summary or "").lower())
    if len(tokens) < 8:
        return False
    uniq_ratio = len(set(tokens)) / len(tokens)
    max_token_repeats = max(tokens.count(t) for t in set(tokens))
    return uniq_ratio < 0.38 or max_token_repeats > max(6, len(tokens) // 3)


def parse_datetime(date_text: str):
    if not date_text:
        return None
    try:
        dt = parsedate_to_datetime(date_text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def find_child_text(item: ET.Element, tag_candidates):
    for tag in tag_candidates:
        el = item.find(tag)
        if el is not None and el.text:
            return el.text.strip()
    return ""


def parse_rss(xml_content: bytes):
    root = ET.fromstring(xml_content)
    items = []

    channel = root.find("channel")
    if channel is not None:
        raw_items = channel.findall("item")
    else:
        atom_entries = root.findall("{http://www.w3.org/2005/Atom}entry")
        raw_items = atom_entries

    for item in raw_items:
        title = find_child_text(item, ["title", "{http://www.w3.org/2005/Atom}title"])
        link = find_child_text(item, ["link"])
        if not link:
            atom_link = item.find("{http://www.w3.org/2005/Atom}link")
            if atom_link is not None:
                link = atom_link.attrib.get("href", "")

        description = find_child_text(
            item,
            [
                "description",
                "summary",
                "{http://www.w3.org/2005/Atom}summary",
                "{http://purl.org/rss/1.0/modules/content/}encoded",
            ],
        )
        pub_date = find_child_text(
            item,
            ["pubDate", "published", "{http://www.w3.org/2005/Atom}updated"],
        )

        if not title or not link:
            continue

        items.append(
            {
                "title": strip_html(title),
                "link": link.strip(),
                "description": strip_html(description),
                "published_at": parse_datetime(pub_date),
            }
        )
    return items


def fetch_source_news(source_key: str, source_cfg: dict, limit: int):
    rss_url = source_cfg["rss_url"]
    try:
        with urlopen(rss_url, timeout=10) as response:
            xml_content = response.read()
        entries = parse_rss(xml_content)
    except (URLError, ET.ParseError, TimeoutError):
        entries = []

    for entry in entries:
        entry["source_key"] = source_key
        entry["source_name"] = source_cfg["name"]

    entries.sort(
        key=lambda x: x["published_at"] or datetime.fromtimestamp(0, tz=timezone.utc),
        reverse=True,
    )
    return entries[:limit]


@lru_cache(maxsize=4)
def load_summarizer(model_key: str):
    model_path = MODEL_PATHS[model_key]
    if not os.path.isdir(model_path):
        raise FileNotFoundError(f"Model path not found: {model_path}")
    if AutoTokenizer is None or AutoModelForSeq2SeqLM is None:
        raise RuntimeError("transformers and torch are required for summarization.")

    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_path, local_files_only=True)

    if torch is not None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = model.to(device)
        # bart_large-cnn in this workspace is fp16; force fp32 on CPU to avoid degenerate decoding.
        if device == "cpu":
            model = model.float()
    else:
        device = "cpu"
    model.eval()
    return tokenizer, model, device


def summarize_text(text: str, model_key: str):
    text = (text or "").strip()
    if not text:
        return ""
    if len(text) > MAX_INPUT_CHARS:
        text = text[:MAX_INPUT_CHARS]

    try:
        tokenizer, model, device = load_summarizer(model_key)
        inputs = tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=1024,
        )
        if torch is not None:
            inputs = {k: v.to(device) for k, v in inputs.items()}

        generate_kwargs = {
            "max_length": DEFAULT_SUMMARY_TOKENS,
            "min_length": 20,
            "length_penalty": 1.5,
            "num_beams": 4,
            "no_repeat_ngram_size": 3,
            "repetition_penalty": 1.1,
            "early_stopping": True,
        }
        if model_key == "bart_large_cnn":
            generate_kwargs.update(
                {
                    "max_length": 120,
                    "min_length": 32,
                    "length_penalty": 2.0,
                    "num_beams": 6,
                    "no_repeat_ngram_size": 4,
                    "repetition_penalty": 1.2,
                }
            )

        with torch.no_grad() if torch is not None else nullcontext():
            output_ids = model.generate(
                **inputs,
                **generate_kwargs,
            )

        summary = tokenizer.decode(output_ids[0], skip_special_tokens=True).strip()
        if is_degenerate_summary(summary):
            return extractive_fallback(text)
        return summary if summary else text[:240] + "..."
    except Exception:
        return extractive_fallback(text)


class nullcontext:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def gather_news(limit_per_source: int, source_filter: str):
    keys = [source_filter] if source_filter in NEWS_SOURCES else list(NEWS_SOURCES.keys())
    all_entries = []

    for key in keys:
        cfg = NEWS_SOURCES[key]
        all_entries.extend(fetch_source_news(key, cfg, limit_per_source))

    all_entries.sort(
        key=lambda x: x["published_at"] or datetime.fromtimestamp(0, tz=timezone.utc),
        reverse=True,
    )
    return all_entries


app = Flask(__name__)


@app.get("/")
def index():
    return render_template(
        "index.html",
        sources=NEWS_SOURCES,
        models=MODEL_PATHS,
        default_model=DEFAULT_MODEL_KEY,
    )


@app.get("/api/news")
def api_news():
    limit = int(request.args.get("limit", 5))
    source = request.args.get("source", "")
    model_key = request.args.get("model", DEFAULT_MODEL_KEY)
    include_raw = request.args.get("include_raw", "false").lower() == "true"

    if model_key not in MODEL_PATHS:
        return jsonify({"error": "Invalid model key", "models": list(MODEL_PATHS.keys())}), 400

    entries = gather_news(limit_per_source=max(1, min(limit, 15)), source_filter=source)
    result = []
    for item in entries:
        text_for_summary = f"{item['title']}. {item['description']}".strip()
        summary = summarize_text(text_for_summary, model_key)
        result.append(
            {
                "title": item["title"],
                "summary": summary,
                "source_name": item["source_name"],
                "source_key": item["source_key"],
                "link": item["link"],
                "published_at": (
                    item["published_at"].isoformat() if item["published_at"] else None
                ),
                "raw_text": text_for_summary if include_raw else None,
            }
        )

    return jsonify(
        {
            "count": len(result),
            "model": model_key,
            "available_models": list(MODEL_PATHS.keys()),
            "available_sources": NEWS_SOURCES,
            "items": result,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=True)
