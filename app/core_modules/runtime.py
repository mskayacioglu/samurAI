"""Shared imports, optional dependencies, and runtime constants."""

import os
import re
import json
import logging
import hashlib
from collections import OrderedDict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from functools import lru_cache
from html import unescape
from threading import Lock
from urllib.parse import quote, quote_plus, unquote, urlencode, urlparse
from urllib.error import URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

try:
    import requests
except ImportError:
    requests = None

try:
    import feedparser
except ImportError:
    feedparser = None

try:
    import trafilatura
except ImportError:
    trafilatura = None

try:
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
except ImportError:
    torch = None
    AutoModelForSeq2SeqLM = None
    AutoTokenizer = None


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
LOGGER = logging.getLogger("core")

MODEL_PATHS = {
    "bart_large_cnn": os.path.join(PROJECT_ROOT, "models", "bart_large-cnn"),
    "bart_base_cnn": os.path.join(PROJECT_ROOT, "models", "bart_base-cnn"),
    "bart_reuters": os.path.join(
        PROJECT_ROOT, "models", "bart_base-reuters", "bart-reuters-best"
    ),
    "mbart50_xlsum": os.path.join(PROJECT_ROOT, "models", "mbart50-xlsum"),
    "mbart-xlsum-2": os.path.join(PROJECT_ROOT, "models", "mbart-xlsum-2"),
    "mt5-xlsum": os.path.join(PROJECT_ROOT, "models", "mt5-xlsum"),
}

DEFAULT_MODEL_KEY = os.getenv("MODEL_KEY", "mbart50_xlsum")
MAX_INPUT_CHARS = int(os.getenv("MAX_INPUT_CHARS", "3500"))
DEFAULT_SUMMARY_TOKENS = int(os.getenv("SUMMARY_MAX_TOKENS", "96"))
ARTICLE_FETCH_TIMEOUT = int(os.getenv("ARTICLE_FETCH_TIMEOUT", "8"))
MAX_ARTICLE_CHARS = int(os.getenv("MAX_ARTICLE_CHARS", "12000"))
MIN_ARTICLE_CHARS = int(os.getenv("MIN_ARTICLE_CHARS", "500"))
SOURCE_OVERSAMPLE_FACTOR = int(os.getenv("SOURCE_OVERSAMPLE_FACTOR", "4"))
SUMMARY_CACHE_SIZE = int(os.getenv("SUMMARY_CACHE_SIZE", "4096"))
DEFAULT_TRANSLATION_MODEL_PATH = os.path.join(
    PROJECT_ROOT, "models", "mbart-large-50-many-to-many-mmt"
)
TRANSLATION_MODEL_REF = os.getenv(
    "TRANSLATION_MODEL_REF",
    DEFAULT_TRANSLATION_MODEL_PATH if os.path.isdir(DEFAULT_TRANSLATION_MODEL_PATH) else "",
)
RSS_FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,tr;q=0.8",
}

SUMMARY_CACHE = OrderedDict()
SUMMARY_CACHE_LOCK = Lock()
ARTICLE_SUMMARY_CACHE = OrderedDict()
ARTICLE_SUMMARY_CACHE_LOCK = Lock()


class nullcontext:
    """Minimal context manager fallback used when torch is unavailable."""

    def __enter__(self):
        """Enter the no-op context manager and return itself."""
        return self

    def __exit__(self, exc_type, exc, tb):
        """Exit the no-op context manager without suppressing exceptions."""
        return False


__all__ = [name for name in globals() if not name.startswith("__")]
