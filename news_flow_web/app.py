import os
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from functools import lru_cache
from html import unescape
from urllib.error import URLError
from urllib.request import Request, urlopen
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
    "mbart50_xlsum": os.path.join(PROJECT_ROOT, "models", "mbart50-xlsum"),
}

DEFAULT_MODEL_KEY = os.getenv("MODEL_KEY", "mbart50_xlsum")
MAX_INPUT_CHARS = int(os.getenv("MAX_INPUT_CHARS", "3500"))
DEFAULT_SUMMARY_TOKENS = int(os.getenv("SUMMARY_MAX_TOKENS", "96"))
ARTICLE_FETCH_TIMEOUT = int(os.getenv("ARTICLE_FETCH_TIMEOUT", "8"))
MAX_ARTICLE_CHARS = int(os.getenv("MAX_ARTICLE_CHARS", "12000"))
MIN_ARTICLE_CHARS = int(os.getenv("MIN_ARTICLE_CHARS", "500"))

LANGUAGE_CONFIGS = {
    "en": {"name": "English", "mbart_lang": "en_XX"},
    "tr": {"name": "Turkce", "mbart_lang": "tr_TR"},
    "fr": {"name": "Francais", "mbart_lang": "fr_XX"},
    "de": {"name": "Deutsch", "mbart_lang": "de_DE"},
    "es": {"name": "Espanol", "mbart_lang": "es_XX"},
    "it": {"name": "Italiano", "mbart_lang": "it_IT"},
    "ru": {"name": "Russkiy", "mbart_lang": "ru_RU"},
    "ar": {"name": "Arabic", "mbart_lang": "ar_AR"},
    "hi": {"name": "Hindi", "mbart_lang": "hi_IN"},
    "zh": {"name": "Chinese", "mbart_lang": "zh_CN"},
    "ja": {"name": "Japanese", "mbart_lang": "ja_XX"},
    "ko": {"name": "Korean", "mbart_lang": "ko_KR"},
    "nl": {"name": "Nederlands", "mbart_lang": "nl_XX"},
    "ro": {"name": "Romana", "mbart_lang": "ro_RO"},
    "vi": {"name": "Vietnamese", "mbart_lang": "vi_VN"},
}

DEFAULT_LANGUAGE_KEY = os.getenv("LANGUAGE_KEY", "en")

NEWS_SOURCES = {
    "bbc_world": {
        "name": "BBC World",
        "rss_url": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "language": "en",
    },
    "guardian_world": {
        "name": "The Guardian World",
        "rss_url": "https://www.theguardian.com/world/rss",
        "language": "en",
    },
    "aljazeera_all": {
        "name": "Al Jazeera",
        "rss_url": "https://www.aljazeera.com/xml/rss/all.xml",
        "language": "en",
    },
    "cnn_world": {
        "name": "CNN World",
        "rss_url": "http://rss.cnn.com/rss/edition_world.rss",
        "language": "en",
    },
    "reuters_world": {
        "name": "Reuters World",
        "rss_url": "https://feeds.reuters.com/Reuters/worldNews",
        "language": "en",
    },
    "npr_world": {
        "name": "NPR World",
        "rss_url": "https://feeds.npr.org/1004/rss.xml",
        "language": "en",
    },
    "dw_world": {
        "name": "DW World",
        "rss_url": "https://rss.dw.com/xml/rss-en-world",
        "language": "en",
    },
    "tr_trthaber": {
        "name": "TRT Haber",
        "rss_url": "https://www.trthaber.com/sondakika.rss",
        "language": "tr",
    },
    "tr_hurriyet": {
        "name": "Hurriyet",
        "rss_url": "https://www.hurriyet.com.tr/rss/anasayfa",
        "language": "tr",
    },
    "tr_ntv": {
        "name": "NTV",
        "rss_url": "https://www.ntv.com.tr/son-dakika.rss",
        "language": "tr",
    },
    "fr_lemonde": {
        "name": "Le Monde",
        "rss_url": "https://www.lemonde.fr/rss/une.xml",
        "language": "fr",
    },
    "fr_lefigaro": {
        "name": "Le Figaro",
        "rss_url": "https://www.lefigaro.fr/rss/figaro_actualites.xml",
        "language": "fr",
    },
    "fr_france24": {
        "name": "France24 FR",
        "rss_url": "https://www.france24.com/fr/rss",
        "language": "fr",
    },
    "de_tagesschau": {
        "name": "Tagesschau",
        "rss_url": "https://www.tagesschau.de/xml/rss2",
        "language": "de",
    },
    "de_spiegel": {
        "name": "Der Spiegel",
        "rss_url": "https://www.spiegel.de/schlagzeilen/index.rss",
        "language": "de",
    },
    "de_faz": {
        "name": "FAZ",
        "rss_url": "https://www.faz.net/rss/aktuell/",
        "language": "de",
    },
    "es_elpais": {
        "name": "El Pais",
        "rss_url": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada",
        "language": "es",
    },
    "es_elmundo": {
        "name": "El Mundo",
        "rss_url": "https://e00-elmundo.uecdn.es/elmundo/rss/portada.xml",
        "language": "es",
    },
    "es_20minutos": {
        "name": "20minutos",
        "rss_url": "https://www.20minutos.es/rss/",
        "language": "es",
    },
    "it_ansa": {
        "name": "ANSA",
        "rss_url": "https://www.ansa.it/sito/ansait_rss.xml",
        "language": "it",
    },
    "it_repubblica": {
        "name": "La Repubblica",
        "rss_url": "https://www.repubblica.it/rss/homepage/rss2.0.xml",
        "language": "it",
    },
    "it_corriere": {
        "name": "Corriere della Sera",
        "rss_url": "https://xml2.corriereobjects.it/rss/homepage.xml",
        "language": "it",
    },
    "ru_lenta": {
        "name": "Lenta",
        "rss_url": "https://lenta.ru/rss/news",
        "language": "ru",
    },
    "ru_tass": {
        "name": "TASS",
        "rss_url": "https://tass.ru/rss/v2.xml",
        "language": "ru",
    },
    "ru_ria": {
        "name": "RIA Novosti",
        "rss_url": "https://ria.ru/export/rss2/archive/index.xml",
        "language": "ru",
    },
    "ar_aljazeera": {
        "name": "Al Jazeera Arabic",
        "rss_url": "https://www.aljazeera.net/aljazeerarss/ar",
        "language": "ar",
    },
    "ar_alarabiya": {
        "name": "Al Arabiya",
        "rss_url": "https://www.alarabiya.net/.mrss/ar.xml",
        "language": "ar",
    },
    "ar_skynewsarabia": {
        "name": "Sky News Arabia",
        "rss_url": "https://www.skynewsarabia.com/web/rss",
        "language": "ar",
    },
    "hi_jagran": {
        "name": "Dainik Jagran",
        "rss_url": "https://www.jagran.com/rss/news/national.xml",
        "language": "hi",
    },
    "hi_bhaskar": {
        "name": "Dainik Bhaskar",
        "rss_url": "https://www.bhaskar.com/rss-v1--category-1061.xml",
        "language": "hi",
    },
    "hi_livehindustan": {
        "name": "Live Hindustan",
        "rss_url": "https://www.livehindustan.com/rss/national/rssfeed.xml",
        "language": "hi",
    },
    "zh_xinhua": {
        "name": "Xinhua",
        "rss_url": "http://www.news.cn/politics/news_politics.xml",
        "language": "zh",
    },
    "zh_chinanews": {
        "name": "China News",
        "rss_url": "https://www.chinanews.com.cn/rss/scroll-news.xml",
        "language": "zh",
    },
    "zh_people": {
        "name": "People CN",
        "rss_url": "http://www.people.com.cn/rss/world.xml",
        "language": "zh",
    },
    "ja_nhk": {
        "name": "NHK",
        "rss_url": "https://www3.nhk.or.jp/rss/news/cat0.xml",
        "language": "ja",
    },
    "ja_asahi": {
        "name": "Asahi",
        "rss_url": "https://www.asahi.com/rss/asahi/newsheadlines.rdf",
        "language": "ja",
    },
    "ja_yomiuri": {
        "name": "Yomiuri",
        "rss_url": "https://www.yomiuri.co.jp/rss/news/cat0.xml",
        "language": "ja",
    },
    "ko_yonhap": {
        "name": "Yonhap",
        "rss_url": "https://www.yna.co.kr/rss/news.xml",
        "language": "ko",
    },
    "ko_hani": {
        "name": "Hankyoreh",
        "rss_url": "https://www.hani.co.kr/rss/",
        "language": "ko",
    },
    "ko_khan": {
        "name": "Kyunghyang",
        "rss_url": "https://www.khan.co.kr/rss/rssdata/total_news.xml",
        "language": "ko",
    },
    "nl_nos": {
        "name": "NOS",
        "rss_url": "https://feeds.nos.nl/nosnieuwsalgemeen",
        "language": "nl",
    },
    "nl_nu": {
        "name": "NU",
        "rss_url": "https://www.nu.nl/rss/Algemeen",
        "language": "nl",
    },
    "nl_volkskrant": {
        "name": "de Volkskrant",
        "rss_url": "https://www.volkskrant.nl/voorpagina/rss.xml",
        "language": "nl",
    },
    "ro_hotnews": {
        "name": "HotNews",
        "rss_url": "https://hotnews.ro/rss",
        "language": "ro",
    },
    "ro_digi24": {
        "name": "Digi24",
        "rss_url": "https://www.digi24.ro/rss",
        "language": "ro",
    },
    "ro_g4media": {
        "name": "G4Media",
        "rss_url": "https://www.g4media.ro/feed",
        "language": "ro",
    },
    "vi_vnexpress": {
        "name": "VNExpress",
        "rss_url": "https://vnexpress.net/rss/tin-moi-nhat.rss",
        "language": "vi",
    },
    "vi_tuoitre": {
        "name": "Tuoi Tre",
        "rss_url": "https://tuoitre.vn/rss/tin-moi-nhat.rss",
        "language": "vi",
    },
    "vi_thanhnien": {
        "name": "Thanh Nien",
        "rss_url": "https://thanhnien.vn/rss/home.rss",
        "language": "vi",
    },
}


def normalize_text(text: str) -> str:
    text = unescape(text or "")
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def strip_html(text: str) -> str:
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", text)
    return normalize_text(clean)


def _sanitize_html_fragment(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return normalize_text(text)


def extract_article_text(html_text: str) -> str:
    if not html_text:
        return ""

    cleaned = re.sub(
        r"(?is)<(script|style|noscript|svg|template|iframe|form|nav|footer)[^>]*>.*?</\1>",
        " ",
        html_text,
    )

    candidates = []
    for block in re.findall(r"(?is)<article\b[^>]*>(.*?)</article>", cleaned):
        block_paragraphs = [
            _sanitize_html_fragment(p)
            for p in re.findall(r"(?is)<p\b[^>]*>(.*?)</p>", block)
        ]
        block_paragraphs = [p for p in block_paragraphs if len(p) >= 50]
        if block_paragraphs:
            candidates.append(" ".join(block_paragraphs))

    if candidates:
        best = max(candidates, key=len)
        if len(best) >= MIN_ARTICLE_CHARS:
            return best[:MAX_ARTICLE_CHARS]

    paragraphs = [
        _sanitize_html_fragment(p) for p in re.findall(r"(?is)<p\b[^>]*>(.*?)</p>", cleaned)
    ]
    filtered = []
    for p in paragraphs:
        if len(p) < 60:
            continue
        low = p.lower()
        if "cookie" in low and "consent" in low:
            continue
        if "subscribe" in low and "newsletter" in low:
            continue
        filtered.append(p)

    if filtered:
        combined = " ".join(filtered)
        return combined[:MAX_ARTICLE_CHARS]
    return ""


@lru_cache(maxsize=256)
def fetch_article_text(url: str) -> str:
    if not url:
        return ""
    try:
        req = Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                )
            },
        )
        with urlopen(req, timeout=ARTICLE_FETCH_TIMEOUT) as response:
            content_type = (response.headers.get("Content-Type") or "").lower()
            if "text/html" not in content_type:
                return ""
            html_bytes = response.read(MAX_ARTICLE_CHARS * 3)
    except Exception:
        return ""

    html_text = html_bytes.decode("utf-8", errors="ignore")
    return extract_article_text(html_text)


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


def summarize_text(text: str, model_key: str, language_key: str):
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
        elif model_key == "mbart50_xlsum":
            language = LANGUAGE_CONFIGS.get(language_key, LANGUAGE_CONFIGS["en"])
            mbart_lang = language["mbart_lang"]
            tokenizer.src_lang = mbart_lang
            forced_bos_token_id = tokenizer.lang_code_to_id.get(mbart_lang)
            generate_kwargs.update(
                {
                    "max_length": 90,
                    "min_length": 24,
                    "length_penalty": 1.1,
                    "num_beams": 5,
                }
            )
            if forced_bos_token_id is not None:
                generate_kwargs["forced_bos_token_id"] = forced_bos_token_id

        with torch.no_grad() if torch is not None else nullcontext():
            output_ids = model.generate(
                **inputs,
                **generate_kwargs,
            )

        summary = tokenizer.decode(output_ids[0], skip_special_tokens=True).strip()
        summary = normalize_text(summary)
        if is_degenerate_summary(summary):
            return normalize_text(extractive_fallback(text))
        return summary if summary else normalize_text(text[:240] + "...")
    except Exception:
        return normalize_text(extractive_fallback(text))


class nullcontext:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def filter_sources_by_language(language_key: str):
    return {
        key: source
        for key, source in NEWS_SOURCES.items()
        if source.get("language") == language_key
    }


def gather_news(limit_per_source: int, language_key: str, selected_sources: list):
    lang_sources = filter_sources_by_language(language_key)
    if selected_sources:
        keys = [k for k in selected_sources if k in lang_sources]
    else:
        keys = list(lang_sources.keys())

    all_entries = []

    for key in keys:
        cfg = lang_sources[key]
        all_entries.extend(fetch_source_news(key, cfg, limit_per_source))

    all_entries.sort(
        key=lambda x: x["published_at"] or datetime.fromtimestamp(0, tz=timezone.utc),
        reverse=True,
    )
    return all_entries


app = Flask(__name__)


@app.get("/")
def index():
    default_language = (
        DEFAULT_LANGUAGE_KEY if DEFAULT_LANGUAGE_KEY in LANGUAGE_CONFIGS else "en"
    )
    return render_template(
        "index.html",
        sources=NEWS_SOURCES,
        languages=LANGUAGE_CONFIGS,
        models=MODEL_PATHS,
        default_model=DEFAULT_MODEL_KEY,
        default_language=default_language,
    )


@app.get("/api/news")
def api_news():
    limit = int(request.args.get("limit", 5))
    source = request.args.get("source", "")
    language = request.args.get("language", DEFAULT_LANGUAGE_KEY)
    model_key = request.args.get("model", DEFAULT_MODEL_KEY)
    sources_param = request.args.get("sources", "")
    include_raw = request.args.get("include_raw", "false").lower() == "true"

    if language not in LANGUAGE_CONFIGS:
        return (
            jsonify(
                {
                    "error": "Invalid language key",
                    "languages": list(LANGUAGE_CONFIGS.keys()),
                }
            ),
            400,
        )

    if model_key not in MODEL_PATHS:
        return jsonify({"error": "Invalid model key", "models": list(MODEL_PATHS.keys())}), 400

    if language != "en" and model_key != "mbart50_xlsum":
        model_key = "mbart50_xlsum"

    selected_sources = []
    if sources_param.strip():
        selected_sources = [s.strip() for s in sources_param.split(",") if s.strip()]
    elif source.strip():
        selected_sources = [source.strip()]

    entries = gather_news(
        limit_per_source=max(1, min(limit, 15)),
        language_key=language,
        selected_sources=selected_sources,
    )
    result = []
    for item in entries:
        article_text = fetch_article_text(item["link"])
        if article_text:
            text_for_summary = f"{item['title']}. {article_text}".strip()
            summary_input_type = "article"
        else:
            text_for_summary = f"{item['title']}. {item['description']}".strip()
            summary_input_type = "rss"
        summary = summarize_text(text_for_summary, model_key, language)
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
                "summary_input_type": summary_input_type,
                "raw_text": text_for_summary if include_raw else None,
            }
        )

    return jsonify(
        {
            "count": len(result),
            "model": model_key,
            "language": language,
            "available_models": list(MODEL_PATHS.keys()),
            "available_sources": NEWS_SOURCES,
            "available_languages": LANGUAGE_CONFIGS,
            "items": result,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=True)
