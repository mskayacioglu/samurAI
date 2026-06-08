"""Local summarization model loading, generation, and summary caching."""

from .runtime import *
from .catalog import *
from .text_processing import *

def extractive_fallback(text: str, max_chars: int = 280, avoid_text: str = "") -> str:
    """Build a short extractive fallback summary from source sentences."""
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return ""
    parts = split_sentences(text)
    usable_parts = [p for p in parts if not (avoid_text and is_near_duplicate_text(p, avoid_text))]
    parts = usable_parts if usable_parts else parts
    picked_parts = []
    for part in parts:
        if not picked_parts:
            if len(part) <= max_chars:
                picked_parts.append(part)
            else:
                return part[:max_chars].rsplit(" ", 1)[0] + "..."
            continue
        combined = " ".join(picked_parts + [part]).strip()
        if len(combined) <= max_chars:
            picked_parts.append(part)
        else:
            break
    picked = " ".join(picked_parts).strip() if picked_parts else (parts[0].strip() if parts else text)
    if len(picked) <= max_chars:
        return picked
    return picked[:max_chars].rsplit(" ", 1)[0] + "..."


def is_degenerate_summary(summary: str) -> bool:
    """Return whether a generated summary is too repetitive to trust."""
    summary = normalize_extracted_text(summary)
    tokens = re.findall(r"\b[\w'-]+\b", summary.lower())
    if len(tokens) < 8:
        cjk_chars = CJK_CHAR_PATTERN.findall(summary)
        if len(cjk_chars) < 16:
            return False
        tokens = [
            "".join(cjk_chars[idx : idx + 2])
            for idx in range(0, max(0, len(cjk_chars) - 1))
        ]
        if len(tokens) < 8:
            return False
    uniq_ratio = len(set(tokens)) / len(tokens)
    max_token_repeats = max(tokens.count(t) for t in set(tokens))
    return uniq_ratio < 0.38 or max_token_repeats > max(6, len(tokens) // 3)



def finalize_summary_text(summary: str, source_text: str) -> str:
    """Ensure summary text ends cleanly or replace it with a fallback."""
    summary = normalize_text(summary)
    if not summary:
        return ""
    if has_sentence_ending(summary):
        return summary

    last_end = max(summary.rfind("."), summary.rfind("!"), summary.rfind("?"), summary.rfind("…"))
    if last_end >= int(len(summary) * 0.55):
        candidate = summary[: last_end + 1].strip()
        if len(candidate) >= 30:
            return candidate

    fallback = normalize_text(extractive_fallback(source_text, max_chars=320))
    if fallback:
        if not has_sentence_ending(fallback):
            fallback = fallback.rstrip(" ,;:-")
            if fallback:
                fallback += "."
        return fallback

    summary = summary.rstrip(" ,;:-")
    return summary + "." if summary else ""


def parse_datetime(date_text: str):
    """Parse an RSS date string into a UTC datetime object."""
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
    """Return text from the first matching direct child tag."""
    for tag in tag_candidates:
        el = item.find(tag)
        if el is not None and el.text:
            return el.text.strip()
    return ""


def _local_name(tag: str) -> str:
    """Return the lowercase local name for a namespaced XML tag."""
    if not tag:
        return ""
    return tag.rsplit("}", 1)[-1].lower()


def find_child_text_anyns(item: ET.Element, name_candidates):
    """Return text from the first child whose local name matches."""
    wanted = {str(name or "").strip().lower() for name in name_candidates if str(name or "").strip()}
    if not wanted:
        return ""
    for child in list(item):
        if _local_name(child.tag) not in wanted:
            continue
        text = "".join(child.itertext()).strip() if child is not None else ""
        if text:
            return text
    return ""


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


def parse_rss_with_feedparser(xml_content: bytes):
    """Parse RSS/Atom bytes with feedparser and return normalized entries."""
    if feedparser is None:
        return []
    try:
        parsed = feedparser.parse(xml_content)
    except Exception:
        return []

    items = []
    for entry in getattr(parsed, "entries", []) or []:
        title = strip_html(getattr(entry, "title", "") or "")
        link = normalize_text(getattr(entry, "link", "") or "")
        if not link:
            links = getattr(entry, "links", []) or []
            for candidate in links:
                href = normalize_text(getattr(candidate, "href", "") or "")
                rel = normalize_text(getattr(candidate, "rel", "")).lower()
                if href and rel in {"", "alternate"}:
                    link = href
                    break
            if not link and links:
                link = normalize_text(getattr(links[0], "href", "") or "")
        if not title or not link:
            continue

        description = (
            getattr(entry, "summary", "")
            or getattr(entry, "description", "")
            or getattr(entry, "content", "")
        )
        if isinstance(description, list) and description:
            description = description[0].get("value", "")
        description = strip_html(str(description or ""))
        published = (
            getattr(entry, "published", "")
            or getattr(entry, "updated", "")
            or getattr(entry, "pubDate", "")
        )
        image_url = ""
        media_content = getattr(entry, "media_content", []) or []
        if media_content:
            image_url = normalize_text(media_content[0].get("url", "") or "")
        if not image_url:
            image_url = extract_image_url_from_html_fragment(str(description or ""))

        items.append(
            {
                "title": title,
                "link": link,
                "description": description,
                "image_url": image_url,
                "published_at": parse_datetime(str(published or "")),
            }
        )
    return items


def parse_rss(xml_content: bytes):
    """Parse RSS or Atom XML bytes into normalized feed entries."""
    if not xml_content:
        return []

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        raw = xml_content
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="ignore")
        raw = str(raw or "")
        raw = raw.lstrip("\ufeff \n\r\t")
        if raw and not raw.startswith("<"):
            idx = raw.find("<")
            raw = raw[idx:] if idx >= 0 else raw

        cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", raw)
        cleaned = re.sub(r"&(?!#?\w+;)", "&amp;", cleaned)
        try:
            root = ET.fromstring(cleaned)
        except ET.ParseError:
            fallback_items = parse_rss_with_feedparser(xml_content)
            if fallback_items:
                return fallback_items
            raise
    items = []

    channel = root.find("channel")
    if channel is not None:
        raw_items = channel.findall("item")
    else:
        atom_entries = root.findall("{http://www.w3.org/2005/Atom}entry")
        raw_items = atom_entries

    for item in raw_items:
        title = find_child_text(item, ["title", "{http://www.w3.org/2005/Atom}title"])
        if not title:
            title = find_child_text_anyns(item, ["title"])
        link = find_child_text(item, ["link"])
        if not link:
            link = find_child_text_anyns(item, ["link"])
        if not link:
            atom_link = item.find("{http://www.w3.org/2005/Atom}link")
            if atom_link is not None:
                link = atom_link.attrib.get("href", "")
        if not link:
            atom_links = [
                node
                for node in item.findall("{http://www.w3.org/2005/Atom}link")
                if normalize_text(node.attrib.get("href", ""))
            ]
            if atom_links:
                preferred = next(
                    (
                        node
                        for node in atom_links
                        if normalize_text(node.attrib.get("rel", "")).lower() in {"", "alternate"}
                    ),
                    atom_links[0],
                )
                link = normalize_text(preferred.attrib.get("href", ""))
        if not link:
            guid = find_child_text_anyns(item, ["guid", "id"])
            if guid and guid.startswith("http"):
                link = guid

        description = find_child_text(
            item,
            [
                "description",
                "summary",
                "{http://www.w3.org/2005/Atom}summary",
                "{http://purl.org/rss/1.0/modules/content/}encoded",
            ],
        )
        if not description:
            description = find_child_text_anyns(item, ["description", "summary", "content", "encoded"])
        pub_date = find_child_text(
            item,
            ["pubDate", "published", "{http://www.w3.org/2005/Atom}updated"],
        )
        if not pub_date:
            pub_date = find_child_text_anyns(item, ["pubdate", "published", "updated"])
        image_url = extract_image_url_from_rss_item(item, description)

        if not title or not link:
            continue

        items.append(
            {
                "title": strip_html(title),
                "link": link.strip(),
                "description": strip_html(description),
                "image_url": image_url,
                "published_at": parse_datetime(pub_date),
            }
        )
    return items


def derive_site_domain(source_cfg: dict) -> str:
    """Derive a publisher domain from source metadata or RSS URLs."""
    explicit = normalize_text(source_cfg.get("site_domain", "")).lower()
    if explicit:
        return explicit

    rss_url = normalize_text(source_cfg.get("rss_url", "")).lower()
    if not rss_url:
        rss_urls = source_cfg.get("rss_urls") or []
        if rss_urls:
            rss_url = normalize_text(rss_urls[0]).lower()
    if not rss_url:
        return ""

    host = normalize_text(urlparse(rss_url).netloc).lower()
    if not host:
        return ""
    host = re.sub(r"^www\d*\.", "", host)
    parts = [p for p in host.split(".") if p]
    if len(parts) >= 3 and parts[0] in {"feeds", "feed", "rss", "news", "xml", "m"}:
        host = ".".join(parts[1:])
    return host


def build_google_fallback_rss_urls(source_key: str, source_cfg: dict):
    """Build Google News RSS fallback URLs for a failing source feed."""
    language = source_cfg.get("language", "en")
    country = source_cfg.get("country") or LANGUAGE_DEFAULT_COUNTRY.get(language, "US")
    topic = source_cfg.get("topic") or "general"
    source_name = normalize_text(source_cfg.get("name", ""))
    domain = derive_site_domain(source_cfg)

    queries = []
    if domain:
        topic_term = topic_query_term(topic, language)
        queries.append(f"site:{domain} {topic_term}")
        queries.append(f"site:{domain} news")
    if source_name:
        queries.append(f'"{source_name}" {topic_query_term(topic, language)}')
    queries.append(source_key.replace("_", " "))

    urls = []
    seen = set()
    for query in queries:
        rss_url = build_google_news_rss_url(query, language, country)
        if rss_url in seen:
            continue
        seen.add(rss_url)
        urls.append(rss_url)
    return urls


def fetch_source_news(source_key: str, source_cfg: dict, limit: int):
    """Fetch and normalize recent news entries from one configured source."""
    rss_urls = source_cfg.get("rss_urls") or [source_cfg["rss_url"]]
    entries = []

    for rss_url in rss_urls:
        try:
            xml_content = b""
            if requests is not None:
                response = requests.get(
                    rss_url,
                    headers=RSS_FETCH_HEADERS,
                    timeout=10,
                    allow_redirects=True,
                )
                if response.ok:
                    xml_content = response.content

            if not xml_content:
                req = Request(rss_url, headers=RSS_FETCH_HEADERS)
                with urlopen(req, timeout=10) as response:
                    xml_content = response.read()

            entries = parse_rss(xml_content)
            if entries:
                break
        except (URLError, ET.ParseError, TimeoutError, ConnectionResetError, OSError) as exc:
            LOGGER.warning(
                "rss_fetch_error source=%s url=%s error=%s",
                source_key,
                rss_url,
                str(exc)[:180],
            )
            continue
        except Exception as exc:
            LOGGER.warning(
                "rss_fetch_error source=%s url=%s error=%s",
                source_key,
                rss_url,
                str(exc)[:180],
            )
            continue

    if not entries:
        fallback_urls = build_google_fallback_rss_urls(source_key, source_cfg)
        for fallback_url in fallback_urls:
            try:
                xml_content = b""
                if requests is not None:
                    response = requests.get(
                        fallback_url,
                        headers=RSS_FETCH_HEADERS,
                        timeout=10,
                        allow_redirects=True,
                    )
                    if response.ok:
                        xml_content = response.content

                if not xml_content:
                    req = Request(fallback_url, headers=RSS_FETCH_HEADERS)
                    with urlopen(req, timeout=10) as response:
                        xml_content = response.read()

                entries = parse_rss(xml_content)
                if entries:
                    LOGGER.info(
                        "rss_fallback_used source=%s fallback=%s entries=%s",
                        source_key,
                        fallback_url,
                        len(entries),
                    )
                    break
            except Exception:
                continue

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
    """Load and cache a local summarization tokenizer and model."""
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
    """Generate a cleaned abstractive summary for normalized source text."""
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
        elif model_key in {"mbart50_xlsum", "mbart-xlsum-2"}:
            language = LANGUAGE_CONFIGS.get(language_key, LANGUAGE_CONFIGS["en"])
            mbart_lang = language["mbart_lang"]
            if hasattr(tokenizer, "src_lang"):
                tokenizer.src_lang = mbart_lang

            forced_bos_token_id = None
            lang_code_map = getattr(tokenizer, "lang_code_to_id", None)
            if isinstance(lang_code_map, dict):
                forced_bos_token_id = lang_code_map.get(mbart_lang)
            if forced_bos_token_id is None and hasattr(tokenizer, "convert_tokens_to_ids"):
                candidate_id = tokenizer.convert_tokens_to_ids(mbart_lang)
                unk_id = getattr(tokenizer, "unk_token_id", None)
                if candidate_id is not None and candidate_id != unk_id:
                    forced_bos_token_id = candidate_id

            generate_kwargs.update(
                {
                    "max_length": 90,
                    "min_length": 24,
                    "length_penalty": 1.1,
                    "num_beams": 5,
                }
            )
            if language_key == "tr":
                generate_kwargs.update(
                    {
                        "max_length": 84,
                        "min_length": 26,
                        "length_penalty": 1.3,
                        "num_beams": 6,
                        "no_repeat_ngram_size": 4,
                        "repetition_penalty": 1.2,
                    }
                )
            if forced_bos_token_id is not None:
                generate_kwargs["forced_bos_token_id"] = forced_bos_token_id
        elif model_key == "mt5-xlsum":
            generate_kwargs.update(
                {
                    "max_length": 84,
                    "min_length": 20,
                    "num_beams": 4,
                    "no_repeat_ngram_size": 2,
                    "length_penalty": 1.0,
                    "repetition_penalty": 1.0,
                }
            )

        with torch.no_grad() if torch is not None else nullcontext():
            output_ids = model.generate(
                **inputs,
                **generate_kwargs,
            )

        summary = tokenizer.decode(output_ids[0], skip_special_tokens=True).strip()
        summary = normalize_text(summary)
        if summary and not has_sentence_ending(summary):
            retry_kwargs = dict(generate_kwargs)
            retry_max = min(180, int(retry_kwargs.get("max_length", DEFAULT_SUMMARY_TOKENS) * 1.4))
            if retry_max > retry_kwargs.get("max_length", DEFAULT_SUMMARY_TOKENS):
                retry_kwargs["max_length"] = retry_max
                retry_min = retry_kwargs.get("min_length", 20)
                retry_kwargs["min_length"] = min(retry_max - 8, retry_min + 8)
                with torch.no_grad() if torch is not None else nullcontext():
                    retry_ids = model.generate(
                        **inputs,
                        **retry_kwargs,
                    )
                retry_summary = normalize_text(
                    tokenizer.decode(retry_ids[0], skip_special_tokens=True).strip()
                )
                if retry_summary and (
                    has_sentence_ending(retry_summary) or len(retry_summary) > len(summary)
                ):
                    summary = retry_summary

        if is_degenerate_summary(summary):
            return finalize_summary_text(extractive_fallback(text), text)
        return finalize_summary_text(summary, text) if summary else finalize_summary_text(text[:240] + "...", text)
    except Exception:
        return finalize_summary_text(extractive_fallback(text), text)


def summarize_text_cached(text: str, model_key: str, language_key: str):
    """Return a cached summary for identical text, model, and language."""
    text = normalize_text(text)
    if not text:
        return ""

    text_hash = hashlib.sha1(text.encode("utf-8")).hexdigest()
    cache_key = (model_key, language_key, text_hash)

    with SUMMARY_CACHE_LOCK:
        cached = SUMMARY_CACHE.get(cache_key)
        if cached is not None:
            SUMMARY_CACHE.move_to_end(cache_key)
            return cached

    summary = summarize_text(text, model_key, language_key)

    with SUMMARY_CACHE_LOCK:
        SUMMARY_CACHE[cache_key] = summary
        SUMMARY_CACHE.move_to_end(cache_key)
        while len(SUMMARY_CACHE) > max(1, SUMMARY_CACHE_SIZE):
            SUMMARY_CACHE.popitem(last=False)
    return summary


def summarize_article_cached(
    text: str, model_key: str, language_key: str, article_key: str = ""
):
    """Return a cached article summary using article identity when available."""
    normalized_key = (article_key or "").strip()
    if normalized_key:
        cache_key = (model_key, language_key, normalized_key)
        with ARTICLE_SUMMARY_CACHE_LOCK:
            cached = ARTICLE_SUMMARY_CACHE.get(cache_key)
            if cached is not None:
                ARTICLE_SUMMARY_CACHE.move_to_end(cache_key)
                return cached

    summary = summarize_text_cached(text, model_key, language_key)

    if normalized_key:
        with ARTICLE_SUMMARY_CACHE_LOCK:
            ARTICLE_SUMMARY_CACHE[cache_key] = summary
            ARTICLE_SUMMARY_CACHE.move_to_end(cache_key)
            while len(ARTICLE_SUMMARY_CACHE) > max(1, SUMMARY_CACHE_SIZE):
                ARTICLE_SUMMARY_CACHE.popitem(last=False)
    return summary



__all__ = [name for name in globals() if not name.startswith("__")]
