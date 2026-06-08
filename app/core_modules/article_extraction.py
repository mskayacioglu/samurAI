"""Article URL resolution, HTML extraction, and image discovery."""

from .runtime import *
from .catalog import *
from .text_processing import *

def strip_html(text: str) -> str:
    """Remove HTML tags and normalize the remaining text."""
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", text)
    return normalize_extracted_text(clean)


def _sanitize_html_fragment(text: str) -> str:
    """Strip tags from an HTML fragment and normalize its text."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    return normalize_extracted_text(text)


def _decode_json_escaped_value(raw_value: str) -> str:
    """Decode a JSON string fragment into normalized text."""
    raw_value = str(raw_value or "")
    if not raw_value:
        return ""
    try:
        decoded = json.loads(f'"{raw_value}"')
    except Exception:
        decoded = raw_value.replace("\\n", " ").replace("\\t", " ").replace('\\"', '"')
    return normalize_extracted_text(decoded)


def _iter_article_bodies_from_json(node):
    """Yield articleBody string values from nested JSON-LD structures."""
    if isinstance(node, dict):
        for key, value in node.items():
            key_name = str(key or "").strip().lower()
            if key_name == "articlebody" and isinstance(value, str):
                yield value
            yield from _iter_article_bodies_from_json(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_article_bodies_from_json(item)


def extract_json_ld_article_texts(html_text: str):
    """Extract article body candidates from JSON-LD script blocks."""
    html_text = str(html_text or "")
    if not html_text:
        return []

    texts = []
    script_blocks = re.findall(
        r'(?is)<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_text,
    )
    for script in script_blocks:
        script = recursive_unescape(script).strip()
        if not script:
            continue
        script = re.sub(r"^\s*<!--|-->\s*$", "", script, flags=re.IGNORECASE).strip()
        script = re.sub(r"^\s*//<!\[CDATA\[|\]\]//\s*$", "", script, flags=re.IGNORECASE).strip()

        parsed = None
        try:
            parsed = json.loads(script)
        except Exception:
            parsed = None

        if parsed is not None:
            texts.extend(_iter_article_bodies_from_json(parsed))
            continue

        # Some sites embed malformed JSON-LD; fallback to escaped string extraction.
        for raw in re.findall(r'(?is)"articleBody"\s*:\s*"((?:\\.|[^"\\]){60,})"', script):
            decoded = _decode_json_escaped_value(raw)
            if decoded:
                texts.append(decoded)

    # Final fallback: direct articleBody key in page source.
    if not texts:
        for raw in re.findall(r'(?is)"articleBody"\s*:\s*"((?:\\.|[^"\\]){60,})"', html_text):
            decoded = _decode_json_escaped_value(raw)
            if decoded:
                texts.append(decoded)

    cleaned = []
    for text in texts:
        normalized = normalize_extracted_text(text)
        if len(normalized) >= 100:
            cleaned.append(normalized)
    return dedupe_text_segments(cleaned)


def _is_link_heavy_paragraph(paragraph_html: str, paragraph_text: str) -> bool:
    """Return whether a paragraph is mostly anchor text."""
    links = re.findall(r"(?is)<a\b[^>]*>(.*?)</a>", paragraph_html or "")
    if not links:
        return False
    link_text = normalize_extracted_text(" ".join(_sanitize_html_fragment(link) for link in links))
    if not link_text:
        return False
    return len(link_text) / max(1, len(paragraph_text)) > 0.72 and len(paragraph_text) < 420


def extract_paragraphs_from_html_block(html_block: str, min_chars: int = 40):
    """Extract cleaned paragraph candidates from an HTML block."""
    html_block = re.sub(
        r"(?is)<(script|style|noscript|svg|template|iframe|form|nav|footer|aside)[^>]*>.*?</\1>",
        " ",
        html_block or "",
    )
    paragraphs = []
    for paragraph_html in re.findall(r"(?is)<p\b[^>]*>(.*?)</p>", html_block):
        paragraph_text = _sanitize_html_fragment(paragraph_html)
        if len(paragraph_text) < min_chars:
            continue
        if _is_link_heavy_paragraph(paragraph_html, paragraph_text):
            continue
        if looks_like_boilerplate(paragraph_text):
            continue
        paragraphs.append(paragraph_text)

    if paragraphs:
        return dedupe_text_segments(paragraphs)

    no_tags = re.sub(r"(?is)<br\s*/?>", "\n", html_block)
    no_tags = re.sub(r"(?is)<[^>]+>", " ", no_tags)
    lines = [
        normalize_extracted_text(line)
        for line in re.split(r"\n+", no_tags)
        if normalize_extracted_text(line)
    ]
    lines = [line for line in lines if len(line) >= max(55, min_chars)]
    lines = [line for line in lines if not looks_like_boilerplate(line)]
    return dedupe_text_segments(lines)


def build_candidate_from_segments(segments):
    """Join useful text segments into one article candidate."""
    segments = dedupe_text_segments(segments or [])
    if not segments:
        return ""
    kept = []
    for segment in segments:
        if len(segment) < 35:
            continue
        if looks_like_boilerplate(segment):
            continue
        if (is_metadata_sentence(segment, "en") or is_metadata_sentence(segment, "tr")) and len(segment) <= 140:
            continue
        kept.append(segment)
    if not kept:
        return ""
    return normalize_extracted_text(" ".join(kept))


def extract_article_text(html_text: str) -> str:
    """Extract the best article body text from raw HTML."""
    if not html_text:
        return ""

    candidates = []
    candidates.extend(extract_json_ld_article_texts(html_text))

    cleaned = re.sub(
        r"(?is)<(script|style|noscript|svg|template|iframe|form|nav|footer|aside)[^>]*>.*?</\1>",
        " ",
        html_text,
    )

    # 1) Prioritize semantic <article> containers.
    for block in re.findall(r"(?is)<article\b[^>]*>(.*?)</article>", cleaned):
        block_paragraphs = extract_paragraphs_from_html_block(block, min_chars=48)
        candidate = build_candidate_from_segments(block_paragraphs)
        if candidate:
            candidates.append(candidate)

    # 2) Many news sites keep body text under content-like containers.
    content_blocks = re.findall(
        r'(?is)<(?:div|section|main)\b[^>]*(?:id|class)\s*=\s*["\'][^"\']*(?:article|content|story|post|body)[^"\']*["\'][^>]*>(.*?)</(?:div|section|main)>',
        cleaned,
    )
    for block in content_blocks:
        block_paragraphs = extract_paragraphs_from_html_block(block, min_chars=38)
        candidate = build_candidate_from_segments(block_paragraphs)
        if candidate:
            candidates.append(candidate)

    # 3) Global paragraph fallback from cleaned DOM.
    paragraph_candidates = extract_paragraphs_from_html_block(cleaned, min_chars=42)
    if paragraph_candidates:
        candidate = build_candidate_from_segments(paragraph_candidates)
        if candidate:
            candidates.append(candidate)

    # 4) Last-resort body text (can be noisy but still useful when everything fails).
    body_match = re.search(r"(?is)<body\b[^>]*>(.*?)</body>", cleaned)
    if body_match:
        body_text = filter_extracted_text_noise(_sanitize_html_fragment(body_match.group(1)))
        if len(body_text) >= 180:
            candidates.append(body_text)

    return pick_best_article_text(candidates)


@lru_cache(maxsize=512)
def fetch_article_text(url: str, source_key: str = "") -> str:
    """Fetch an article URL and return cleaned article body text."""
    if not url:
        return ""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    language_key = infer_language_from_source_key(source_key)
    resolved_url = resolve_article_url(url, headers=headers)
    html_text = ""
    if requests is not None:
        try:
            response = requests.get(
                resolved_url,
                headers=headers,
                timeout=ARTICLE_FETCH_TIMEOUT,
                allow_redirects=True,
            )
            content_type = (response.headers.get("Content-Type") or "").lower()
            if response.ok and (
                "text/html" in content_type or "application/xhtml+xml" in content_type
            ):
                html_bytes = (response.content or b"")[: MAX_ARTICLE_CHARS * 4]
                html_text = decode_html_bytes(
                    html_bytes,
                    content_type=content_type,
                    hint_encoding=(response.encoding or response.apparent_encoding or ""),
                    language_key=language_key,
                )
        except Exception:
            html_text = ""

    if not html_text:
        try:
            req = Request(resolved_url, headers=headers)
            with urlopen(req, timeout=ARTICLE_FETCH_TIMEOUT) as response:
                content_type = (response.headers.get("Content-Type") or "").lower()
                if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                    return ""
                html_bytes = response.read(MAX_ARTICLE_CHARS * 4)
                html_text = decode_html_bytes(
                    html_bytes,
                    content_type=content_type,
                    hint_encoding="",
                    language_key=language_key,
                )
        except Exception:
            html_text = ""

    candidates = []
    if html_text:
        primary = extract_article_text(html_text)
        if primary:
            candidates.append(primary)

        if trafilatura is not None:
            for kwargs in ({"favor_precision": True}, {"favor_recall": True}):
                try:
                    text = trafilatura.extract(
                        html_text,
                        include_comments=False,
                        include_tables=False,
                        **kwargs,
                    )
                except TypeError:
                    text = trafilatura.extract(
                        html_text,
                        include_comments=False,
                        include_tables=False,
                    )
                except Exception:
                    text = ""
                if text:
                    candidates.append(normalize_extracted_text(text))

    best = pick_best_article_text(candidates)
    if best:
        return apply_source_text_cleanup(best, source_key=source_key, source_url=resolved_url)

    # Robust fallback extractor for JS-heavy/complex templates.
    if trafilatura is not None:
        try:
            downloaded = trafilatura.fetch_url(resolved_url)
            if downloaded:
                fallback_candidates = []
                for kwargs in ({"favor_precision": True}, {"favor_recall": True}):
                    try:
                        text = trafilatura.extract(
                            downloaded,
                            include_comments=False,
                            include_tables=False,
                            **kwargs,
                        )
                    except TypeError:
                        text = trafilatura.extract(
                            downloaded,
                            include_comments=False,
                            include_tables=False,
                        )
                    except Exception:
                        text = ""
                    if text:
                        fallback_candidates.append(normalize_extracted_text(text))
                best_fallback = pick_best_article_text(fallback_candidates)
                if best_fallback:
                    return apply_source_text_cleanup(
                        best_fallback,
                        source_key=source_key,
                        source_url=resolved_url,
                    )
        except Exception:
            return ""
    return ""


@lru_cache(maxsize=256)
def fetch_article_image(url: str) -> str:
    """Fetch an article URL and return the best discovered image URL."""
    if not url:
        return ""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    resolved_url = resolve_article_url(url, headers=headers)
    html_text = ""
    if requests is not None:
        try:
            response = requests.get(
                resolved_url,
                headers=headers,
                timeout=ARTICLE_FETCH_TIMEOUT,
                allow_redirects=True,
            )
            content_type = (response.headers.get("Content-Type") or "").lower()
            if response.ok and (
                "text/html" in content_type or "application/xhtml+xml" in content_type
            ):
                html_bytes = (response.content or b"")[: MAX_ARTICLE_CHARS * 2]
                html_text = decode_html_bytes(
                    html_bytes,
                    content_type=content_type,
                    hint_encoding=(response.encoding or response.apparent_encoding or ""),
                )
        except Exception:
            html_text = ""
    if not html_text:
        try:
            req = Request(resolved_url, headers=headers)
            with urlopen(req, timeout=ARTICLE_FETCH_TIMEOUT) as response:
                content_type = (response.headers.get("Content-Type") or "").lower()
                if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                    return ""
                html_bytes = response.read(MAX_ARTICLE_CHARS * 2)
                html_text = decode_html_bytes(html_bytes, content_type=content_type, hint_encoding="")
        except Exception:
            return ""
    return extract_image_from_html(html_text)


def _google_news_base64_id(url: str) -> str:
    """Extract the encoded Google News article id from a URL."""
    try:
        parsed = urlparse(url or "")
        path = [p for p in (parsed.path or "").split("/") if p]
        if parsed.netloc.lower() != "news.google.com":
            return ""
        if len(path) < 2:
            return ""
        if path[-2] not in {"rss", "articles", "read"} and "articles" not in path:
            return ""
        return path[-1]
    except Exception:
        return ""


def decode_google_news_url(url: str, headers: dict) -> str:
    """Resolve a Google News wrapper URL to its publisher URL when possible."""
    if requests is None:
        return ""
    base64_id = _google_news_base64_id(url)
    if not base64_id:
        return ""

    signature = ""
    timestamp = ""
    for candidate in [
        f"https://news.google.com/articles/{base64_id}",
        f"https://news.google.com/rss/articles/{base64_id}",
    ]:
        try:
            response = requests.get(
                candidate,
                headers=headers,
                timeout=max(3, ARTICLE_FETCH_TIMEOUT),
                allow_redirects=True,
            )
            if not response.ok:
                continue
            html = response.text or ""
            sg_match = re.search(r'data-n-a-sg="([^"]+)"', html)
            ts_match = re.search(r'data-n-a-ts="([^"]+)"', html)
            if sg_match and ts_match:
                signature = normalize_text(sg_match.group(1))
                timestamp = normalize_text(ts_match.group(1))
                break
        except Exception:
            continue

    if not signature or not timestamp:
        return ""

    try:
        payload = [
            "Fbv4je",
            (
                '["garturlreq",[['
                '"X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,null,null,0,1],'
                '"X","X",1,[1,1,1],1,1,null,0,0,null,0],'
                f'"{base64_id}",{timestamp},"{signature}"]'
            ),
        ]
        request_body = "f.req=" + quote(json.dumps([[payload]]), safe="")
        response = requests.post(
            "https://news.google.com/_/DotsSplashUi/data/batchexecute",
            headers={
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "User-Agent": headers.get("User-Agent", "Mozilla/5.0"),
                "Referer": "https://news.google.com/",
            },
            data=request_body,
            timeout=max(3, ARTICLE_FETCH_TIMEOUT),
        )
        if not response.ok:
            return ""

        parts = (response.text or "").split("\n\n")
        if len(parts) < 2:
            return ""
        parsed = json.loads(parts[1])[:-2]
        if not parsed:
            return ""
        decoded_url = json.loads(parsed[0][2])[1]
        decoded_url = normalize_text(decoded_url)
        if not decoded_url:
            return ""
        decoded_host = urlparse(decoded_url).netloc.lower()
        if decoded_host and "news.google.com" not in decoded_host:
            return decoded_url
    except Exception:
        return ""
    return ""


def resolve_article_url(url: str, headers: dict) -> str:
    """Resolve Google News links while leaving publisher URLs unchanged."""
    if not url:
        return url
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        host = ""
    if "news.google.com" not in host:
        return url
    if requests is None:
        return url
    decoded = decode_google_news_url(url, headers=headers)
    if decoded:
        return decoded
    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=max(3, ARTICLE_FETCH_TIMEOUT),
            allow_redirects=True,
        )
        final_url = response.url or url
        final_host = urlparse(final_url).netloc.lower()
        if "news.google.com" not in final_host:
            return final_url

        html = response.text or ""
        candidates = re.findall(r"https?://[^\s\"'<>\\\\]+", html)
        for candidate in candidates:
            candidate = normalize_text(unquote(candidate))
            cand_host = urlparse(candidate).netloc.lower()
            if not cand_host:
                continue
            if "news.google.com" in cand_host:
                continue
            if "google.com" in cand_host or "gstatic.com" in cand_host:
                continue
            return candidate
    except Exception:
        return url
    return url


def extract_image_url_from_html_fragment(fragment: str) -> str:
    """Extract the first image URL from an HTML fragment."""
    if not fragment:
        return ""
    m = re.search(r'(?is)<img[^>]+src=["\']([^"\']+)["\']', fragment)
    if not m:
        return ""
    return normalize_text(m.group(1))


def extract_image_url_from_rss_item(item: ET.Element, description: str) -> str:
    """Extract image media from an RSS item or its description HTML."""
    media_ns = "{http://search.yahoo.com/mrss/}"

    for tag in ["enclosure", f"{media_ns}content", f"{media_ns}thumbnail"]:
        for el in item.findall(tag):
            url = normalize_text(el.attrib.get("url", ""))
            mime = (el.attrib.get("type") or "").lower()
            if url and (not mime or "image" in mime):
                return url

    for group in item.findall(f"{media_ns}group"):
        for child_tag in [f"{media_ns}content", f"{media_ns}thumbnail"]:
            for el in group.findall(child_tag):
                url = normalize_text(el.attrib.get("url", ""))
                mime = (el.attrib.get("type") or "").lower()
                if url and (not mime or "image" in mime):
                    return url

    return extract_image_url_from_html_fragment(description)


def extract_image_from_html(html_text: str) -> str:
    """Extract a representative image URL from HTML metadata or article body."""
    if not html_text:
        return ""

    for pattern in [
        r'(?is)<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'(?is)<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'(?is)<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        r'(?is)<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
    ]:
        m = re.search(pattern, html_text)
        if m and m.group(1):
            return normalize_text(m.group(1))

    m = re.search(r'(?is)<article\b[^>]*>.*?<img[^>]+src=["\']([^"\']+)["\']', html_text)
    if m and m.group(1):
        return normalize_text(m.group(1))
    return ""



__all__ = [name for name in globals() if not name.startswith("__")]
