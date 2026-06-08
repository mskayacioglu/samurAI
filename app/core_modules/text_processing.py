"""Text normalization, de-duplication, and article cleanup helpers."""

from .runtime import *
from .catalog import *

def normalize_text(text: str) -> str:
    """Normalize HTML entities, non-breaking spaces, and repeated whitespace."""
    text = unescape(text or "")
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


MOJIBAKE_MARKERS = (
    "â",
    "Ã",
    "Â",
    "\u00e3\u0080",
    "\u00e3\u0081",
    "\u00e3\u0082",
    "\u00e3\u0083",
    "\u00e4\u00b8",
    "\u00e5\u00ad",
    "\u00e6\u0097",
    "\u00f0\u009f",
)
COMMON_UTF8_MOJIBAKE_SEQUENCES = (
    "ÄŸ",
    "Äž",
    "Ä±",
    "Ä°",
    "ÅŸ",
    "Åž",
    "Ã¼",
    "Ãœ",
    "Ã¶",
    "Ã–",
    "Ã§",
    "Ã‡",
    "Ã¢",
    "Ãª",
    "Ã®",
    "Ã»",
    "â€™",
    "â€œ",
    "â€",
    "â€“",
    "â€”",
    "â€¦",
)
BOILERPLATE_PATTERNS = [
    r"\bcookie(?:s)?\b",
    r"\bprivacy policy\b",
    r"\bterms of use\b",
    r"\bsubscribe\b",
    r"\bsubscription\b",
    r"\bnewsletter\b",
    r"\badvertisement\b",
    r"\bsponsored\b",
    r"\bsign in\b",
    r"\blog in\b",
    r"\bmost read\b",
    r"\brelated (?:articles?|stories)\b",
    r"\bshare this\b",
    r"\bclick here\b",
    r"\bçerez(?:ler)?\b",
    r"\bgizlilik politikası\b",
    r"\bkullanım koşulları\b",
    r"\bkişisel veriler(?:in korunması)?\b",
    r"\babone ol\b",
    r"\büye ol\b",
    r"\breklam\b",
    r"\bsponsorlu\b",
    r"\bdaha fazla oku\b",
    r"\ben çok okunanlar\b",
    r"\baccessibility links\b",
    r"\bopen navigation menu\b",
    r"\bclose navigation menu\b",
    r"\bexpand/collapse submenu\b",
    r"\bskip to main content\b",
    r"\bskip to content\b",
    r"\bskip links?\b",
    r"\bkeyboard shortcuts for audio player\b",
    r"\bnpr shop\b",
    r"\breklamsız cumhuriyet\b",
    r"\bcumhuriyet tv\b",
    r"\bson dakika türkiye haberleri\b",
    r"\bdolar\s+\d",
    r"\beuro\s+\d",
    r"\bsterlin\s+\d",
    r"\bbitcoin\s+\d",
    r"\bgram altın\b",
]
SHORT_NAV_PATTERNS = [
    r"\bhaberler\b",
    r"\bvideo\b",
    r"\bfoto(?:ğraf|galeri)\b",
    r"\bcanlı\b",
    r"\bgündem\b",
    r"\bekonomi\b",
    r"\bspor\b",
    r"\bweather\b",
    r"\btravel\b",
    r"\bmenu\b",
]
NAV_CLUSTER_WORDS = {
    "home",
    "news",
    "national",
    "world",
    "politics",
    "business",
    "health",
    "science",
    "climate",
    "culture",
    "books",
    "movies",
    "television",
    "music",
    "podcasts",
    "shows",
    "newsletters",
    "shop",
    "gündem",
    "yazarlar",
    "siyaset",
    "ekonomi",
    "dünya",
    "yaşam",
    "kültür",
    "sanat",
    "eğitim",
    "teknoloji",
    "yerel",
    "egazete",
    "reklamsız",
    "cumhuriyet",
}
CODE_NOISE_PATTERNS = [
    r"/\*!\s*sc\*/",
    r"\bdata-styled\b",
    r"\bobject-fit\s*:",
    r"\bfont-family\s*:",
    r"\bposition\s*:\s*(?:absolute|relative|fixed)\b",
    r"\b@media\s+screen\b",
    r"\bdisplay\s*:\s*(?:block|flex|grid)\b",
    r'\{"@context"',
    r'"@context"\s*:\s*"https?://schema\.org"',
    r'"@type"\s*:\s*"(?:liveblogposting|newsarticle|imageobject|breadcrumblist|organization)"',
    r'"contenturl"\s*:',
    r"<(?:div|a|span|li|ul|script|style)\b",
    r"<path\b",
    r"\bcurrentcolor\b",
    r"\baria-label\s*=",
    r"\bdatetime\s*=",
]

GENERIC_ARTICLE_TEXT_CLEANUP_PATTERNS = [
    r"\b(read more|continue reading|devamı için tıklayın)\b",
    r"\b(this is a developing story|story continues below)\b",
    r"\bfollow us on (?:twitter|x|facebook|instagram|telegram)\b",
    r"\bjoin our (?:newsletter|channel)\b",
    r"\brelated (?:stories|news|articles?)\b",
    r"(?i)(?:menu|メニュー)\s*(?:close|閉じる)",
]

DOMAIN_TEXT_CLEANUP_PATTERNS = {
    "bbc.com": [
        r"\bget all the latest .*? on the bbc\b",
        r"\blisten to this article\b",
    ],
    "cnn.com": [
        r"\bwatch this video\b",
        r"\bcnn's .*? newsletter\b",
    ],
    "hurriyet.com.tr": [
        r"\bhürriyet\.com\.tr'ye dön\b",
        r"\bson dakika haberleri için tıklayınız\b",
    ],
    "ntv.com.tr": [
        r"\bntv uygulamasını indir\b",
    ],
    "trthaber.com": [
        r"\btrt haber mobil uygulamasını\b",
    ],
    "vnexpress.net": [
        r"\bxem thêm\b",
    ],
}

SOURCE_TEXT_CLEANUP_PATTERNS = {
    "tr_hurriyet": [
        r"\bHürriyet Gazetecilik ve Matbaacılık A\.Ş\.\b",
        r"\bHürriyet Son Dakika\b",
    ],
    "tr_ntv": [
        r"\bntv\.com\.tr farkıyla\b",
    ],
    "fr_lemonde": [
        r"\ble monde avec afp\b",
    ],
    "de_spiegel": [
        r"\bspiegel\+ abonnieren\b",
    ],
    "es_elpais": [
        r"\blea también\b",
    ],
    "it_repubblica": [
        r"\bcontinua a leggere\b",
    ],
    "ru_ria": [
        r"\bчитайте также\b",
    ],
    "ja_nhk": [
        r"\bNHK NEWS WEB\b",
    ],
}


def recursive_unescape(text: str, rounds: int = 4) -> str:
    """Repeatedly HTML-unescape text until it stabilizes or reaches a limit."""
    value = str(text or "")
    for _ in range(max(1, rounds)):
        decoded = unescape(value)
        if decoded == value:
            break
        value = decoded
    return value


def mojibake_count(text: str) -> int:
    """Count markers that indicate likely mojibake encoding artifacts."""
    text = str(text or "")
    marker_hits = sum(text.count(marker) for marker in MOJIBAKE_MARKERS)
    marker_hits += sum(text.count(marker) for marker in COMMON_UTF8_MOJIBAKE_SEQUENCES)
    marker_hits += len(re.findall(r"[\u00c2\u00c3\u00e2\u00e3][\u0080-\u00bf]", text))
    marker_hits += len(re.findall(r"[\u00e4-\u00e9][\u0080-\u00bf]{2,}", text))
    return marker_hits


def repair_mojibake(text: str) -> str:
    """Try common byte-decoding repairs for garbled UTF-8 text."""
    text = str(text or "")
    original_bad = mojibake_count(text)
    if original_bad == 0:
        return text
    best = text
    best_bad = original_bad
    for source_encoding in ("latin-1", "cp1252", "cp1254"):
        try:
            repaired = text.encode(source_encoding).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        repaired_bad = mojibake_count(repaired)
        has_strong_cjk_signal = cjk_char_count(repaired) >= 6
        similar_length = len(repaired) >= int(len(text) * 0.9)
        if repaired_bad < best_bad and (similar_length or has_strong_cjk_signal):
            best = repaired
            best_bad = repaired_bad
    return best


def normalize_extracted_text(text: str) -> str:
    """Normalize extracted article text after entity and encoding cleanup."""
    text = recursive_unescape(text)
    text = repair_mojibake(text)
    text = text.replace("\u200b", " ")
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]", " ", text)
    return normalize_text(text)


SENTENCE_BOUNDARY_PATTERN = re.compile(r"(?<=[.!?…。！？؟])\s*")
CJK_CHAR_PATTERN = re.compile(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7a3]")


def split_sentences(text: str):
    """Split normalized text into sentence-like chunks."""
    text = normalize_extracted_text(text)
    if not text:
        return []
    parts = [part.strip() for part in SENTENCE_BOUNDARY_PATTERN.split(text) if part.strip()]
    return parts if parts else [text]


def cjk_char_count(text: str) -> int:
    """Return the number of CJK characters in text."""
    return len(CJK_CHAR_PATTERN.findall(text or ""))


def word_like_count(text: str) -> int:
    """Estimate word count while accounting for CJK text."""
    text = normalize_extracted_text(text)
    if not text:
        return 0
    latin_like_words = re.findall(r"\b[\w'-]+\b", text)
    cjk_units = cjk_char_count(text) // 2
    return max(len(latin_like_words), cjk_units)


def looks_like_code_noise(text: str) -> bool:
    """Return whether text resembles code or serialized page noise."""
    text = str(text or "")
    if not text:
        return False
    low = text.lower()
    if any(re.search(pattern, low, flags=re.IGNORECASE) for pattern in CODE_NOISE_PATTERNS):
        return True
    brace_count = text.count("{") + text.count("}")
    semi_count = text.count(";")
    colon_count = text.count(":")
    if brace_count >= 2 and semi_count >= 2 and colon_count >= 3:
        return True
    if text.count('{"') >= 2 and text.count('":') >= 5:
        return True
    if text.count('","') >= 5 and text.count(":") >= 8:
        return True
    if len(text) <= 240 and re.search(r"\b(?:function|const|let|var)\b", low):
        return True
    return False


def looks_like_boilerplate(text: str) -> bool:
    """Return whether text appears to be navigation or boilerplate content."""
    sentence = normalize_extracted_text(text).lower()
    if not sentence:
        return True
    if looks_like_code_noise(sentence):
        return True
    if any(re.search(pattern, sentence, flags=re.IGNORECASE) for pattern in BOILERPLATE_PATTERNS):
        return True
    if len(sentence) <= 420:
        cluster_hits = sum(1 for word in NAV_CLUSTER_WORDS if f" {word} " in f" {sentence} ")
        if cluster_hits >= 6:
            return True
    if len(sentence) <= 64:
        nav_hits = sum(
            1 for pattern in SHORT_NAV_PATTERNS if re.search(pattern, sentence, flags=re.IGNORECASE)
        )
        if nav_hits >= 2:
            return True
    return False


def dedupe_text_segments(segments):
    """Return text segments with near-duplicate neighbors removed."""
    deduped = []
    for segment in segments:
        segment = normalize_extracted_text(segment)
        if not segment:
            continue
        if any(is_near_duplicate_text(segment, prev, threshold=0.9) for prev in deduped[-8:]):
            continue
        deduped.append(segment)
    return deduped


def filter_extracted_text_noise(text: str) -> str:
    """Remove boilerplate, metadata, duplicate, and code-like text fragments."""
    text = normalize_extracted_text(text)
    if not text:
        return ""
    chunks = []
    for block in re.split(r"\n+|\s+\|\s+", text):
        block = normalize_extracted_text(block)
        if not block:
            continue
        chunks.extend(split_sentences(block))
    if not chunks:
        return text

    kept = []
    for chunk in chunks:
        if len(chunk) < 18:
            continue
        if looks_like_code_noise(chunk):
            continue
        if looks_like_boilerplate(chunk):
            continue
        if (is_metadata_sentence(chunk, "en") or is_metadata_sentence(chunk, "tr")) and len(chunk) <= 140:
            continue
        if any(is_near_duplicate_text(chunk, prev, threshold=0.92) for prev in kept[-6:]):
            continue
        kept.append(chunk)

    if not kept:
        return "" if looks_like_boilerplate(text) else text
    filtered = normalize_extracted_text(" ".join(kept))
    if len(filtered) < max(80, int(len(text) * 0.35)):
        if looks_like_boilerplate(text):
            return filtered
        return text
    return filtered


def score_article_candidate(text: str) -> float:
    """Score how likely extracted text is to be useful article body content."""
    text = normalize_extracted_text(text)
    if not text:
        return -10_000.0

    sentences = split_sentences(text)
    words = word_like_count(text)
    alpha_chars = len(
        re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿÇĞİÖŞÜçğıöşüА-Яа-я一-龯ぁ-んァ-ン]", text)
    )
    alpha_ratio = alpha_chars / max(1, len(text))
    boiler_hits = sum(
        len(re.findall(pattern, text, flags=re.IGNORECASE)) for pattern in BOILERPLATE_PATTERNS
    )
    code_hits = sum(len(re.findall(pattern, text, flags=re.IGNORECASE)) for pattern in CODE_NOISE_PATTERNS)
    mojibake_hits = mojibake_count(text)
    duplicate_sentences = max(0, len(sentences) - len(dedupe_text_segments(sentences)))

    score = min(len(text), MAX_ARTICLE_CHARS) * 0.12
    score += len(sentences) * 32
    score += alpha_ratio * 170
    score -= boiler_hits * 180
    score -= code_hits * 260
    score -= mojibake_hits * 85
    score -= duplicate_sentences * 130

    if len(text) < 160:
        score -= 320
    if words < 40:
        score -= 120
    if len(sentences) < 2:
        score -= 140
    return score


def pick_best_article_text(candidates):
    """Select the highest-scoring cleaned article text from candidates."""
    scored = []
    for candidate in candidates:
        cleaned_candidate = filter_extracted_text_noise(candidate)
        cleaned_candidate = normalize_extracted_text(cleaned_candidate)
        if not cleaned_candidate:
            continue
        scored.append((score_article_candidate(cleaned_candidate), cleaned_candidate))
    if not scored:
        return ""
    scored.sort(key=lambda item: (item[0], len(item[1])), reverse=True)
    return scored[0][1][:MAX_ARTICLE_CHARS]


def _extract_charset(content_type: str) -> str:
    """Extract a charset value from an HTTP Content-Type header."""
    match = re.search(r"charset\s*=\s*([A-Za-z0-9._-]+)", content_type or "", flags=re.IGNORECASE)
    return (match.group(1) if match else "").strip()


def _extract_meta_charset(raw_bytes: bytes) -> str:
    """Extract charset metadata from the beginning of an HTML byte stream."""
    if not raw_bytes:
        return ""
    # Meta tags are ASCII-compatible; parse from a short head slice.
    head = raw_bytes[:16384].decode("ascii", errors="ignore")
    patterns = [
        r'(?is)<meta\b[^>]*charset=["\']?\s*([A-Za-z0-9._-]+)',
        r'(?is)<meta\b[^>]*http-equiv=["\']content-type["\'][^>]*content=["\'][^"\']*charset\s*=\s*([A-Za-z0-9._-]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, head)
        if match:
            return normalize_text(match.group(1)).lower()
    return ""


def infer_language_from_source_key(source_key: str) -> str:
    """Infer a language key from source config or source key prefix."""
    key = normalize_text(source_key)
    if not key:
        return ""
    cfg = NEWS_SOURCES.get(key)
    if cfg:
        lang = normalize_text(cfg.get("language", "")).lower()
        if lang in LANGUAGE_CONFIGS:
            return lang
    prefix = key.split("_", 1)[0].lower()
    return prefix if prefix in LANGUAGE_CONFIGS else ""


def decode_html_bytes(
    raw_bytes: bytes,
    content_type: str = "",
    hint_encoding: str = "",
    language_key: str = "",
) -> str:
    """Decode HTML bytes using headers, metadata, and language-aware fallbacks."""
    if not raw_bytes:
        return ""

    encodings = []
    language_key = normalize_text(language_key).lower()
    cjk_language = language_key in {"ja", "ko", "zh"}
    meta_charset = _extract_meta_charset(raw_bytes)
    header_charset = _extract_charset(content_type)
    cjk_hint_text = " ".join([meta_charset, header_charset, hint_encoding]).lower()
    cjk_encoding_hint = any(
        token in cjk_hint_text
        for token in (
            "shift_jis",
            "shift-jis",
            "sjis",
            "cp932",
            "euc-jp",
            "iso-2022-jp",
            "cp949",
            "euc-kr",
            "gb18030",
            "gbk",
            "gb2312",
            "big5",
        )
    )

    for candidate in [
        meta_charset,
        header_charset,
        "utf-8",
        hint_encoding,
        "cp1254",
        "cp1252",
        "latin-1",
    ]:
        candidate = normalize_text(candidate).lower()
        if candidate and candidate not in encodings:
            encodings.append(candidate)

    if cjk_language or (not language_key and cjk_encoding_hint):
        for candidate in [
            "cp932",
            "shift_jis",
            "euc-jp",
            "cp949",
            "euc-kr",
            "gb18030",
            "gbk",
            "big5",
        ]:
            if candidate not in encodings:
                encodings.append(candidate)

    utf8_is_valid = False
    try:
        raw_bytes.decode("utf-8", errors="strict")
        utf8_is_valid = True
    except UnicodeDecodeError:
        utf8_is_valid = False

    best_text = ""
    best_score = float("-inf")
    for encoding in encodings:
        try:
            decoded = raw_bytes.decode(encoding, errors="replace")
        except LookupError:
            continue
        normalized = normalize_extracted_text(decoded)
        if not normalized:
            continue
        cjk_chars = cjk_char_count(normalized)
        score = -normalized.count("�") * 8 - mojibake_count(normalized) * 4 + len(normalized) * 0.001
        if encoding == "utf-8" and utf8_is_valid:
            score += 6.0
        if cjk_language:
            score += cjk_chars * 0.35
            if language_key == "ja":
                kana_chars = len(re.findall(r"[\u3040-\u30ff]", normalized))
                hangul_chars = len(re.findall(r"[\uac00-\ud7af]", normalized))
                if hangul_chars > 12 and hangul_chars > kana_chars * 0.6:
                    score -= min(420.0, hangul_chars * 8.0)
        else:
            # For non-CJK sources, CJK-heavy text is usually a mis-decoding artifact.
            if cjk_chars > 8:
                score -= min(420.0, cjk_chars * 6.0)
            mixed_cjk = len(re.findall(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]", normalized))
            if mixed_cjk >= 3:
                score -= min(320.0, mixed_cjk * 14.0)
        if encoding in {"latin-1", "iso-8859-1", "cp1252"} and cjk_chars == 0:
            score -= 1.5
        if score > best_score:
            best_score = score
            best_text = normalized
    return best_text


def _word_set(text: str) -> set:
    """Return normalized significant words from text."""
    return {t for t in re.findall(r"\b[\w'-]+\b", (text or "").lower()) if len(t) > 2}


def is_near_duplicate_text(a: str, b: str, threshold: float = 0.82) -> bool:
    """Return whether two text snippets overlap above a word threshold."""
    a_norm = normalize_text(a).lower()
    b_norm = normalize_text(b).lower()
    if not a_norm or not b_norm:
        return False
    if a_norm == b_norm:
        return True

    a_words = _word_set(a_norm)
    b_words = _word_set(b_norm)
    if not a_words or not b_words:
        return False

    overlap = len(a_words & b_words) / max(1, min(len(a_words), len(b_words)))
    return overlap >= threshold


def contains_datetime_like(text: str) -> bool:
    """Return whether text contains date or time-like fragments."""
    text = normalize_text(text).lower()
    if not text:
        return False

    patterns = [
        r"\b[0-3]?\d[./-][0-1]?\d[./-](?:\d{4}|\d{2})\b",
        r"\b\d{4}[./-][0-1]?\d[./-][0-3]?\d\b",
        r"\b[0-2]?\d:[0-5]\d\b",
        r"\b(?:ocak|subat|şubat|mart|nisan|mayis|mayıs|haziran|temmuz|agustos|ağustos|eylul|eylül|ekim|kasim|kasım|aralik|aralık)\b",
        r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\b",
    ]
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def is_metadata_sentence(text: str, language_key: str) -> bool:
    """Return whether a sentence is likely publish/update metadata."""
    sentence = normalize_text(text).lower()
    if not sentence:
        return True
    if len(sentence) > 240:
        return False

    common_markers = [
        "last updated",
        "updated:",
        "published:",
        "publish date",
        "publication date",
        "giriş tarihi",
        "yayınlanma tarihi",
        "yayinlanma tarihi",
        "güncelleme tarihi",
        "guncelleme tarihi",
        "son güncelleme",
        "son guncelleme",
        "oluşturulma tarihi",
        "olusturulma tarihi",
    ]
    tr_markers = [
        "giriş:",
        "yayınlanma:",
        "yayinlanma:",
        "güncellenme:",
        "guncellenme:",
        "saat:",
    ]
    markers = list(common_markers)
    if language_key == "tr":
        markers.extend(tr_markers)

    has_marker = any(marker in sentence for marker in markers)
    has_datetime = contains_datetime_like(sentence)

    if has_marker and (has_datetime or len(sentence) <= 110):
        return True
    if has_datetime:
        token_count = len(re.findall(r"\b[\w'-]+\b", sentence))
        if token_count <= 7 and len(sentence) <= 64:
            return True
    if has_datetime and re.search(r"\b(date|updated|published|giriş|yayın|yayin|güncelle|guncelle|saat)\b", sentence):
        return True
    if re.fullmatch(r"[\d\s:./\-|]+", sentence):
        return True
    return False


def _source_cleanup_patterns(source_key: str = "", source_url: str = ""):
    """Return generic and source-specific cleanup regex patterns."""
    patterns = list(GENERIC_ARTICLE_TEXT_CLEANUP_PATTERNS)
    source_key = normalize_text(source_key)
    if source_key and source_key in SOURCE_TEXT_CLEANUP_PATTERNS:
        patterns.extend(SOURCE_TEXT_CLEANUP_PATTERNS[source_key])

    host = normalize_text(urlparse(source_url or "").netloc).lower()
    host = re.sub(r"^www\d*\.", "", host)
    if host:
        for domain, domain_patterns in DOMAIN_TEXT_CLEANUP_PATTERNS.items():
            if host.endswith(domain):
                patterns.extend(domain_patterns)
    return patterns


def apply_source_text_cleanup(text: str, source_key: str = "", source_url: str = "") -> str:
    """Apply source-specific article cleanup rules to text."""
    cleaned = normalize_extracted_text(text)
    if not cleaned:
        return ""
    for pattern in _source_cleanup_patterns(source_key, source_url):
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,-|")
    return cleaned


def strip_leading_metadata_prefix(text: str) -> str:
    """Remove a leading publish/update metadata prefix from a sentence."""
    sentence = normalize_text(text)
    if not sentence:
        return ""

    marker = (
        r"(?:giriş(?: tarihi)?|yayınlanma tarihi|yayinlanma tarihi|"
        r"son güncelleme|son guncelleme|güncelleme tarihi|guncelleme tarihi|"
        r"updated|last updated|published)"
    )
    datetime_chunk = (
        r"(?:"
        r"\d{1,2}[./-]\d{1,2}[./-](?:\d{4}|\d{2})"
        r"|\d{4}[./-]\d{1,2}[./-]\d{1,2}"
        r"|(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},?\s+\d{4}"
        r"|(?:ocak|subat|şubat|mart|nisan|mayis|mayıs|haziran|temmuz|agustos|ağustos|eylul|eylül|ekim|kasim|kasım|aralik|aralık)\s+\d{1,2}\s+\d{4}"
        r")(?:\s+[0-2]?\d:[0-5]\d)?"
    )
    pattern = rf"^\s*{marker}\s*[:\-]\s*(?:{datetime_chunk})?\s*(?:[|–—-]\s*)?"
    return re.sub(pattern, "", sentence, flags=re.IGNORECASE).strip()


def clean_article_for_summarization(
    text: str,
    language_key: str,
    title: str = "",
    source_key: str = "",
    source_url: str = "",
) -> str:
    """Clean article body text before it is sent to a summarization model."""
    text = apply_source_text_cleanup(text, source_key=source_key, source_url=source_url)
    if not text:
        return ""

    if language_key == "tr":
        # Remove common Turkish news metadata fragments that hurt summary quality.
        patterns = [
            r"\bGiriş Tarihi\s*:\s*(?:[0-3]?\d[./-][0-1]?\d[./-](?:\d{4}|\d{2})(?:\s+[0-2]?\d:[0-5]\d)?|[^|]{1,40})",
            r"\bSon Güncelleme\s*:\s*(?:[0-3]?\d[./-][0-1]?\d[./-](?:\d{4}|\d{2})(?:\s+[0-2]?\d:[0-5]\d)?|[^|]{1,40})",
            r"\bYayınlanma Tarihi\s*:\s*(?:[0-3]?\d[./-][0-1]?\d[./-](?:\d{4}|\d{2})(?:\s+[0-2]?\d:[0-5]\d)?|[^|]{1,40})",
            r"\bGüncelleme Tarihi\s*:\s*(?:[0-3]?\d[./-][0-1]?\d[./-](?:\d{4}|\d{2})(?:\s+[0-2]?\d:[0-5]\d)?|[^|]{1,40})",
            r"\b[0-3]?\d\.[0-1]?\d\.\d{4}\s+[0-2]?\d:[0-5]\d\b",
            r"\bFoto(?:ğraf|graf)\s*:\s*[^.]{1,100}",
            r"\bKaynak\s*:\s*[^.]{1,100}",
            r"(?<!\w)EN ÇOK OKUNANLAR(?:\s*[:|–—-]\s*)?",
            r"(?<!\w)SON DAK[İI]KA(?:\s+HABERLER[İI])?(?:\s*[:|–—-]\s*)",
            r"[^.]{0,120}\bhesab[ıiuü]ndan konuya ilişkin açıklama yapıldı\.?",
            r"\b\w+n[ıiuü]n,\s*[A-Za-zÇĞİÖŞÜçğıöşü0-9'\" ]{0,40}hesab[ıiuü]ndan konuya ilişkin açıklama yapıldı\.?",
        ]
        for pattern in patterns:
            text = re.sub(pattern, " ", text, flags=re.IGNORECASE)

    # Many pages repeat the exact headline at the start of the article body.
    # Remove leading sentence(s) that are near-duplicates of the title.
    if title:
        parts = split_sentences(text)
        while parts and is_near_duplicate_text(parts[0], title):
            # Keep lead sentences that include substantial new details after the title.
            lead = normalize_text(parts[0])
            title_norm = normalize_text(title)
            lead_tokens = re.findall(r"\b[\w'-]+\b", lead.lower())
            title_tokens = re.findall(r"\b[\w'-]+\b", title_norm.lower())
            extra_tokens = max(0, len(lead_tokens) - len(title_tokens))
            if extra_tokens >= 8 or len(lead) >= int(len(title_norm) * 1.45):
                break
            parts = parts[1:]
        if parts:
            text = " ".join(parts)

    # Filter out metadata-only sentences (timestamps, publish/update labels).
    sentence_parts = []
    for block in re.split(r"\s+\|\s+", text):
        sentence_parts.extend(split_sentences(block))
    if sentence_parts:
        kept = []
        for idx, sentence in enumerate(sentence_parts):
            sentence = strip_leading_metadata_prefix(sentence)
            if not sentence:
                continue
            if is_metadata_sentence(sentence, language_key) and idx < 6:
                continue
            kept.append(sentence)
        if kept:
            text = " ".join(kept)

    text = apply_source_text_cleanup(text, source_key=source_key, source_url=source_url)
    text = re.sub(r"\s+", " ", text).strip(" .,-")
    return text




def has_sentence_ending(text: str) -> bool:
    """Return whether text ends with a sentence-final punctuation mark."""
    text = normalize_text(text)
    if not text:
        return False
    return bool(re.search(r"[.!?…][\"')\]]*$", text)) or text.endswith(("。", "؟", "！", "؟", "…"))
def postprocess_summary(summary: str, title: str, language_key: str) -> str:
    """Clean generated summary text and reject title-only outputs."""
    summary = normalize_text(summary)
    title = normalize_text(title)
    if not summary:
        return summary

    # Remove duplicated headline prefix from generated summary when possible.
    if title:
        low_summary = summary.lower()
        low_title = title.lower()
        if low_summary.startswith(low_title):
            tail = summary[len(title) :].lstrip(" .:-")
            if len(tail) >= 24:
                summary = tail[0].upper() + tail[1:] if tail else summary
        elif is_near_duplicate_text(summary, title):
            return ""

    processed = clean_article_for_summarization(summary, language_key, title=title)
    if processed and not has_sentence_ending(processed) and has_sentence_ending(summary):
        processed = processed.rstrip(" ,;:-")
        if processed:
            processed += "."
    return processed

__all__ = [name for name in globals() if not name.startswith("__")]
