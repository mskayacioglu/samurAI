"""RSS parsing and source feed fetching helpers."""

from .runtime import *
from .catalog import *
from .text_processing import *
from .article_extraction import (
    extract_image_url_from_html_fragment,
    extract_image_url_from_rss_item,
    strip_html,
)

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



__all__ = [name for name in globals() if not name.startswith("__")]
