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

from flask import Flask, jsonify, render_template, request

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


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
LOGGER = logging.getLogger(__name__)

MODEL_PATHS = {
    "bart_large_cnn": os.path.join(PROJECT_ROOT, "models", "bart_large-cnn"),
    "bart_base_cnn": os.path.join(PROJECT_ROOT, "models", "bart_base-cnn"),
    "bart_reuters": os.path.join(
        PROJECT_ROOT, "models", "bart_base-reuters", "bart-reuters-best"
    ),
    "mbart50_xlsum": os.path.join(PROJECT_ROOT, "models", "mbart50-xlsum"),
    "mt5-xlsum": os.path.join(PROJECT_ROOT, "models", "mT5_multilingual_XLSum"),
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

SUMMARY_CACHE = OrderedDict()
SUMMARY_CACHE_LOCK = Lock()
ARTICLE_SUMMARY_CACHE = OrderedDict()
ARTICLE_SUMMARY_CACHE_LOCK = Lock()

TOP_NEWS_SOURCES = {
    "en": [
        {"key": "bbc_world", "name": "BBC World", "rss_url": "https://feeds.bbci.co.uk/news/world/rss.xml"},
        {"key": "guardian_world", "name": "The Guardian World", "rss_url": "https://www.theguardian.com/world/rss"},
        {"key": "reuters_world", "name": "Reuters World", "rss_url": "https://feeds.reuters.com/Reuters/worldNews"},
        {"key": "cnn_world", "name": "CNN World", "rss_url": "http://rss.cnn.com/rss/edition_world.rss"},
        {"key": "npr_world", "name": "NPR World", "rss_url": "https://feeds.npr.org/1004/rss.xml"},
        {"key": "aljazeera_world", "name": "Al Jazeera", "rss_url": "https://www.aljazeera.com/xml/rss/all.xml"},
        {"key": "dw_world", "name": "DW World", "rss_url": "https://rss.dw.com/xml/rss-en-world"},
        {"key": "nyt_world", "name": "NYTimes World", "rss_url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"},
        {"key": "fox_world", "name": "Fox News World", "rss_url": "https://moxie.foxnews.com/google-publisher/world.xml"},
        {"key": "sky_world", "name": "Sky News World", "rss_url": "https://feeds.skynews.com/feeds/rss/world.xml"},
    ],
    "tr": [
        {"key": "tr_trthaber", "name": "TRT Haber", "rss_url": "https://www.trthaber.com/sondakika.rss"},
        {"key": "tr_hurriyet", "name": "Hurriyet", "rss_url": "https://www.hurriyet.com.tr/rss/anasayfa"},
        {"key": "tr_ntv", "name": "NTV", "rss_url": "https://www.ntv.com.tr/son-dakika.rss"},
        {"key": "tr_haberturk", "name": "Haberturk", "rss_url": "https://www.haberturk.com/rss"},
        {"key": "tr_sozcu", "name": "Sozcu Gundem", "rss_url": "https://www.sozcu.com.tr/rss/gundem.xml"},
        {"key": "tr_sabah", "name": "Sabah", "rss_url": "https://www.sabah.com.tr/rss/anasayfa.xml"},
        {"key": "tr_cnnturk", "name": "CNN Turk", "rss_url": "https://www.cnnturk.com/feed/rss/turkiye/news"},
        {
            "key": "tr_milliyet",
            "name": "Milliyet",
            "rss_url": "https://www.milliyet.com.tr/rss/rssnew/gundem.xml",
            "rss_urls": [
                "https://www.milliyet.com.tr/rss/rssnew/gundem.xml",
                "https://www.milliyet.com.tr/rss/rssnew/sondakikarss.xml",
            ],
        },
        {"key": "tr_cumhuriyet", "name": "Cumhuriyet", "rss_url": "https://www.cumhuriyet.com.tr/rss"},
        {"key": "tr_aa", "name": "Anadolu Ajansi", "rss_url": "https://www.aa.com.tr/tr/rss/default?cat=guncel"},
    ],
    "fr": [
        {"key": "fr_lemonde", "name": "Le Monde", "rss_url": "https://www.lemonde.fr/rss/une.xml"},
        {"key": "fr_lefigaro", "name": "Le Figaro", "rss_url": "https://www.lefigaro.fr/rss/figaro_actualites.xml"},
        {"key": "fr_france24", "name": "France24 FR", "rss_url": "https://www.france24.com/fr/rss"},
        {"key": "fr_liberation", "name": "Liberation", "rss_url": "https://www.liberation.fr/arc/outboundfeeds/rss-all/?outputType=xml"},
        {"key": "fr_20minutes", "name": "20 Minutes FR", "rss_url": "https://www.20minutes.fr/feeds/rss-une.xml"},
        {"key": "fr_ouestfrance", "name": "Ouest France", "rss_url": "https://www.ouest-france.fr/rss-en-continu.xml"},
        {"key": "fr_rfi", "name": "RFI FR", "rss_url": "https://www.rfi.fr/fr/rss"},
        {"key": "fr_lexpress", "name": "L'Express", "rss_url": "https://www.lexpress.fr/rss/alaune.xml"},
        {"key": "fr_leparisien", "name": "Le Parisien", "rss_url": "https://feeds.leparisien.fr/leparisien/rss/actualites"},
        {"key": "fr_euronews", "name": "Euronews FR", "rss_url": "https://fr.euronews.com/rss?format=mrss"},
    ],
    "de": [
        {"key": "de_tagesschau", "name": "Tagesschau", "rss_url": "https://www.tagesschau.de/xml/rss2"},
        {"key": "de_spiegel", "name": "Der Spiegel", "rss_url": "https://www.spiegel.de/schlagzeilen/index.rss"},
        {"key": "de_faz", "name": "FAZ", "rss_url": "https://www.faz.net/rss/aktuell/"},
        {"key": "de_welt", "name": "Die Welt", "rss_url": "https://www.welt.de/feeds/latest.rss"},
        {"key": "de_zeit", "name": "Die Zeit", "rss_url": "https://newsfeed.zeit.de/index"},
        {"key": "de_sueddeutsche", "name": "Sueddeutsche", "rss_url": "https://rss.sueddeutsche.de/rss/Topthemen"},
        {"key": "de_ntv", "name": "n-tv", "rss_url": "https://www.n-tv.de/rss"},
        {"key": "de_dlf", "name": "Deutschlandfunk", "rss_url": "https://www.deutschlandfunk.de/nachrichten-100.rss"},
        {"key": "de_handelsblatt", "name": "Handelsblatt", "rss_url": "https://www.handelsblatt.com/contentexport/feed/schlagzeilen"},
        {"key": "de_bild", "name": "BILD", "rss_url": "https://www.bild.de/rssfeeds/vw-neu/vw-neu-16725514,view=rss2.bild.xml"},
    ],
    "es": [
        {"key": "es_elpais", "name": "El Pais", "rss_url": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada"},
        {"key": "es_elmundo", "name": "El Mundo", "rss_url": "https://e00-elmundo.uecdn.es/elmundo/rss/portada.xml"},
        {"key": "es_abc", "name": "ABC", "rss_url": "https://www.abc.es/rss/feeds/abcPortada.xml"},
        {"key": "es_lavanguardia", "name": "La Vanguardia", "rss_url": "https://www.lavanguardia.com/rss/home.xml"},
        {"key": "es_20minutos", "name": "20minutos", "rss_url": "https://www.20minutos.es/rss/"},
        {"key": "es_publico", "name": "Publico", "rss_url": "https://www.publico.es/rss/"},
        {"key": "es_eldiario", "name": "elDiario", "rss_url": "https://www.eldiario.es/rss/"},
        {"key": "es_rtve", "name": "RTVE", "rss_url": "https://www.rtve.es/rss/"},
        {"key": "es_elconfidencial", "name": "El Confidencial", "rss_url": "https://rss.elconfidencial.com/espana/"},
        {"key": "es_europapress", "name": "Europa Press", "rss_url": "https://www.europapress.es/rss/rss.aspx"},
    ],
    "it": [
        {"key": "it_ansa", "name": "ANSA", "rss_url": "https://www.ansa.it/sito/ansait_rss.xml"},
        {"key": "it_repubblica", "name": "La Repubblica", "rss_url": "https://www.repubblica.it/rss/homepage/rss2.0.xml"},
        {"key": "it_corriere", "name": "Corriere della Sera", "rss_url": "https://xml2.corriereobjects.it/rss/homepage.xml"},
        {"key": "it_sole24", "name": "Il Sole 24 Ore", "rss_url": "https://www.ilsole24ore.com/rss/primapagina.xml"},
        {"key": "it_lastampa", "name": "La Stampa", "rss_url": "https://www.lastampa.it/rss/home.xml"},
        {"key": "it_tgcom24", "name": "TGCOM24", "rss_url": "https://www.tgcom24.mediaset.it/rss/homepage.xml"},
        {"key": "it_rainews", "name": "Rai News", "rss_url": "https://www.rainews.it/dl/rainews/rss/atom.xml"},
        {"key": "it_fanpage", "name": "Fanpage", "rss_url": "https://www.fanpage.it/feed/"},
        {"key": "it_agi", "name": "AGI", "rss_url": "https://www.agi.it/rss"},
        {"key": "it_adnkronos", "name": "Adnkronos", "rss_url": "https://www.adnkronos.com/RSS_Speciali.xml"},
    ],
    "ru": [
        {"key": "ru_tass", "name": "TASS", "rss_url": "https://tass.ru/rss/v2.xml"},
        {"key": "ru_ria", "name": "RIA Novosti", "rss_url": "https://ria.ru/export/rss2/archive/index.xml"},
        {"key": "ru_lenta", "name": "Lenta", "rss_url": "https://lenta.ru/rss/news"},
        {"key": "ru_rt", "name": "RT Russian", "rss_url": "https://russian.rt.com/rss"},
        {"key": "ru_gazeta", "name": "Gazeta", "rss_url": "https://www.gazeta.ru/export/rss/lenta.xml"},
        {"key": "ru_kommersant", "name": "Kommersant", "rss_url": "https://www.kommersant.ru/RSS/news.xml"},
        {"key": "ru_rg", "name": "Rossiyskaya Gazeta", "rss_url": "https://rg.ru/xml/index.xml"},
        {"key": "ru_iz", "name": "Izvestia", "rss_url": "https://iz.ru/xml/rss/all.xml"},
        {"key": "ru_interfax", "name": "Interfax", "rss_url": "https://www.interfax.ru/rss.asp"},
        {"key": "ru_vedomosti", "name": "Vedomosti", "rss_url": "https://www.vedomosti.ru/rss/news"},
    ],
    "ar": [
        {"key": "ar_aljazeera", "name": "Al Jazeera Arabic", "rss_url": "https://www.aljazeera.net/aljazeerarss/ar"},
        {"key": "ar_alarabiya", "name": "Al Arabiya", "rss_url": "https://www.alarabiya.net/.mrss/ar.xml"},
        {"key": "ar_skynewsarabia", "name": "Sky News Arabia", "rss_url": "https://www.skynewsarabia.com/web/rss"},
        {"key": "ar_bbc", "name": "BBC Arabic", "rss_url": "https://feeds.bbci.co.uk/arabic/rss.xml"},
        {"key": "ar_france24", "name": "France24 Arabic", "rss_url": "https://www.france24.com/ar/rss"},
        {"key": "ar_rt", "name": "RT Arabic", "rss_url": "https://arabic.rt.com/rss/"},
        {"key": "ar_aawsat", "name": "Asharq Al-Awsat", "rss_url": "https://aawsat.com/home/feed"},
        {"key": "ar_cnn", "name": "CNN Arabic", "rss_url": "https://arabic.cnn.com/feed"},
        {"key": "ar_independent", "name": "Independent Arabic", "rss_url": "https://www.independentarabia.com/rss.xml"},
        {"key": "ar_euronews", "name": "Euronews Arabic", "rss_url": "https://arabic.euronews.com/rss"},
    ],
    "hi": [
        {"key": "hi_jagran", "name": "Dainik Jagran", "rss_url": "https://www.jagran.com/rss/news/national.xml"},
        {"key": "hi_bhaskar", "name": "Dainik Bhaskar", "rss_url": "https://www.bhaskar.com/rss-v1--category-1061.xml"},
        {"key": "hi_livehindustan", "name": "Live Hindustan", "rss_url": "https://www.livehindustan.com/rss/national/rssfeed.xml"},
        {"key": "hi_aajtak", "name": "Aaj Tak", "rss_url": "https://www.aajtak.in/rssfeeds/?id=home"},
        {"key": "hi_amarujala", "name": "Amar Ujala", "rss_url": "https://www.amarujala.com/rss/national.xml"},
        {"key": "hi_ndtvindia", "name": "NDTV India", "rss_url": "https://feeds.feedburner.com/ndtvkhabar-latest"},
        {"key": "hi_bbchindi", "name": "BBC Hindi", "rss_url": "https://feeds.bbci.co.uk/hindi/rss.xml"},
        {"key": "hi_zee", "name": "Zee News Hindi", "rss_url": "https://zeenews.india.com/hindi/rss/india-national-news.xml"},
        {"key": "hi_abp", "name": "ABP Hindi", "rss_url": "https://www.abplive.com/home/feed"},
        {"key": "hi_indiatv", "name": "India TV Hindi", "rss_url": "https://www.indiatv.in/rssnews/topstory.xml"},
    ],
    "zh": [
        {"key": "zh_xinhua", "name": "Xinhua", "rss_url": "http://www.news.cn/politics/news_politics.xml"},
        {"key": "zh_chinanews", "name": "China News", "rss_url": "https://www.chinanews.com.cn/rss/scroll-news.xml"},
        {"key": "zh_people", "name": "People CN", "rss_url": "http://www.people.com.cn/rss/world.xml"},
        {"key": "zh_ifeng", "name": "ifeng", "rss_url": "https://news.ifeng.com/rss/index.xml"},
        {"key": "zh_sohu", "name": "Sohu", "rss_url": "https://rss.sohu.com/rss/news.xml"},
        {"key": "zh_cctv", "name": "CCTV", "rss_url": "http://news.cctv.com/rss/china.xml"},
        {"key": "zh_globaltimes", "name": "Global Times CN", "rss_url": "https://www.globaltimes.cn/rss/outbrain.xml"},
        {"key": "zh_stcn", "name": "STCN", "rss_url": "https://news.stcn.com/rss/index.xml"},
        {"key": "zh_zaobao", "name": "Zaobao", "rss_url": "https://www.zaobao.com.sg/realtime/china/rss.xml"},
        {"key": "zh_huanqiu", "name": "Huanqiu", "rss_url": "https://rss.huanqiu.com/china.xml"},
    ],
    "ja": [
        {"key": "ja_nhk", "name": "NHK", "rss_url": "https://www3.nhk.or.jp/rss/news/cat0.xml"},
        {"key": "ja_asahi", "name": "Asahi", "rss_url": "https://www.asahi.com/rss/asahi/newsheadlines.rdf"},
        {"key": "ja_yomiuri", "name": "Yomiuri", "rss_url": "https://www.yomiuri.co.jp/rss/news/cat0.xml"},
        {"key": "ja_mainichi", "name": "Mainichi", "rss_url": "https://mainichi.jp/rss/etc/mainichi-flash.rss"},
        {"key": "ja_nikkei", "name": "Nikkei", "rss_url": "https://www.nikkei.com/rss/news.rss"},
        {"key": "ja_sankei", "name": "Sankei", "rss_url": "https://www.sankei.com/rss/news/flash.xml"},
        {"key": "ja_jiji", "name": "Jiji", "rss_url": "https://www.jiji.com/rss/ranking.rdf"},
        {"key": "ja_tokyo", "name": "Tokyo Shimbun", "rss_url": "https://www.tokyo-np.co.jp/rss"},
        {"key": "ja_47news", "name": "47News", "rss_url": "https://www.47news.jp/rss/all.xml"},
        {"key": "ja_tbs", "name": "TBS News", "rss_url": "https://newsdig.tbs.co.jp/list/rss.xml"},
    ],
    "ko": [
        {"key": "ko_yonhap", "name": "Yonhap", "rss_url": "https://www.yna.co.kr/rss/news.xml"},
        {"key": "ko_hani", "name": "Hankyoreh", "rss_url": "https://www.hani.co.kr/rss/"},
        {"key": "ko_khan", "name": "Kyunghyang", "rss_url": "https://www.khan.co.kr/rss/rssdata/total_news.xml"},
        {"key": "ko_chosun", "name": "Chosun", "rss_url": "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml"},
        {"key": "ko_joongang", "name": "JoongAng", "rss_url": "https://rss.joins.com/joins_news_list.xml"},
        {"key": "ko_donga", "name": "DongA", "rss_url": "https://rss.donga.com/total.xml"},
        {"key": "ko_kbs", "name": "KBS", "rss_url": "https://news.kbs.co.kr/rss/rss.xml"},
        {"key": "ko_sbs", "name": "SBS", "rss_url": "https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=01"},
        {"key": "ko_mbc", "name": "MBC", "rss_url": "https://imnews.imbc.com/rss/news/news_00.xml"},
        {"key": "ko_seoul", "name": "Seoul Shinmun", "rss_url": "https://www.seoul.co.kr/rss/news.xml"},
    ],
    "nl": [
        {"key": "nl_nos", "name": "NOS", "rss_url": "https://feeds.nos.nl/nosnieuwsalgemeen"},
        {"key": "nl_nu", "name": "NU", "rss_url": "https://www.nu.nl/rss/Algemeen"},
        {"key": "nl_volkskrant", "name": "de Volkskrant", "rss_url": "https://www.volkskrant.nl/voorpagina/rss.xml"},
        {"key": "nl_trouw", "name": "Trouw", "rss_url": "https://www.trouw.nl/rss.xml"},
        {"key": "nl_nrc", "name": "NRC", "rss_url": "https://www.nrc.nl/rss/"},
        {"key": "nl_telegraaf", "name": "De Telegraaf", "rss_url": "https://www.telegraaf.nl/rss"},
        {"key": "nl_ad", "name": "AD", "rss_url": "https://www.ad.nl/rss.xml"},
        {"key": "nl_parool", "name": "Parool", "rss_url": "https://www.parool.nl/rss.xml"},
        {"key": "nl_rtl", "name": "RTL Nieuws", "rss_url": "https://www.rtlnieuws.nl/rss.xml"},
        {"key": "nl_bnr", "name": "BNR", "rss_url": "https://www.bnr.nl/rss/nieuws"},
    ],
    "ro": [
        {"key": "ro_hotnews", "name": "HotNews", "rss_url": "https://hotnews.ro/rss"},
        {"key": "ro_digi24", "name": "Digi24", "rss_url": "https://www.digi24.ro/rss"},
        {"key": "ro_g4media", "name": "G4Media", "rss_url": "https://www.g4media.ro/feed"},
        {"key": "ro_adevarul", "name": "Adevarul", "rss_url": "https://adevarul.ro/rss"},
        {"key": "ro_mediafax", "name": "Mediafax", "rss_url": "https://www.mediafax.ro/rss"},
        {"key": "ro_protv", "name": "Stirile ProTV", "rss_url": "https://stirileprotv.ro/rss/"},
        {"key": "ro_ziare", "name": "Ziare", "rss_url": "https://www.ziare.com/rss"},
        {"key": "ro_antena3", "name": "Antena 3", "rss_url": "https://www.antena3.ro/rss"},
        {"key": "ro_libertatea", "name": "Libertatea", "rss_url": "https://www.libertatea.ro/feed"},
        {"key": "ro_euronews", "name": "Euronews RO", "rss_url": "https://ro.euronews.com/rss"},
    ],
    "vi": [
        {"key": "vi_vnexpress", "name": "VNExpress", "rss_url": "https://vnexpress.net/rss/tin-moi-nhat.rss"},
        {"key": "vi_tuoitre", "name": "Tuoi Tre", "rss_url": "https://tuoitre.vn/rss/tin-moi-nhat.rss"},
        {"key": "vi_thanhnien", "name": "Thanh Nien", "rss_url": "https://thanhnien.vn/rss/home.rss"},
        {"key": "vi_vietnamnet", "name": "Vietnamnet", "rss_url": "https://vietnamnet.vn/rss/home.rss"},
        {"key": "vi_dantri", "name": "Dan Tri", "rss_url": "https://dantri.com.vn/rss/home.rss"},
        {"key": "vi_znews", "name": "ZNews", "rss_url": "https://znews.vn/rss/trang-chu.rss"},
        {"key": "vi_vtc", "name": "VTC News", "rss_url": "https://vtcnews.vn/rss/feed.rss"},
        {"key": "vi_nld", "name": "Nguoi Lao Dong", "rss_url": "https://nld.com.vn/rss/home.rss"},
        {"key": "vi_tienphong", "name": "Tien Phong", "rss_url": "https://tienphong.vn/rss/home.rss"},
        {"key": "vi_vov", "name": "VOV", "rss_url": "https://vov.vn/rss/home.rss"},
    ],
}


TOPICAL_SOURCE_EXTENSIONS = {
    "en": [
        {
            "key": "en_bbc_sport",
            "name": "BBC Sport",
            "rss_url": "https://feeds.bbci.co.uk/sport/rss.xml",
            "topic": "sports",
            "country": "GB",
        },
        {
            "key": "en_espn",
            "name": "ESPN",
            "rss_url": "https://www.espn.com/espn/rss/news",
            "topic": "sports",
            "country": "US",
        },
    ],
    "tr": [
        {
            "key": "tr_ntvspor",
            "name": "NTV Spor",
            "rss_url": "https://www.ntvspor.net/rss",
            "rss_urls": [
                "https://www.ntvspor.net/rss",
                "https://www.ntvspor.net/haber/rss",
            ],
            "topic": "sports",
            "country": "TR",
        },
        {
            "key": "tr_hurriyet_spor",
            "name": "Hurriyet Spor",
            "rss_url": "https://www.hurriyet.com.tr/rss/sporarena",
            "rss_urls": [
                "https://www.hurriyet.com.tr/rss/sporarena",
                "https://www.hurriyet.com.tr/rss/spor",
            ],
            "topic": "sports",
            "country": "TR",
        },
        {
            "key": "tr_sabah_spor",
            "name": "Sabah Spor",
            "rss_url": "https://www.sabah.com.tr/rss/spor.xml",
            "topic": "sports",
            "country": "TR",
        },
    ],
    "de": [
        {
            "key": "de_kicker",
            "name": "Kicker",
            "rss_url": "https://newsfeed.kicker.de/news/aktuell",
            "topic": "sports",
            "country": "DE",
        }
    ],
    "es": [
        {
            "key": "es_marca",
            "name": "Marca",
            "rss_url": "https://e00-marca.uecdn.es/rss/portada.xml",
            "topic": "sports",
            "country": "ES",
        }
    ],
    "it": [
        {
            "key": "it_gazzetta",
            "name": "La Gazzetta dello Sport",
            "rss_url": "https://www.gazzetta.it/rss/home.xml",
            "topic": "sports",
            "country": "IT",
        }
    ],
}

UNIQUE_SOURCE_EXTENSIONS = {
    "ar": [
        {"key": "ar_masrawy", "name": "Masrawy", "rss_url": "https://www.masrawy.com/rss", "topic": "general", "country": "EG", "site_domain": "masrawy.com"},
        {"key": "ar_youm7", "name": "Youm7", "rss_url": "https://www.youm7.com/rss/SectionRss?SectionID=65", "topic": "politics", "country": "EG", "site_domain": "youm7.com"},
    ],
    "de": [
        {"key": "de_heise", "name": "Heise", "rss_url": "https://www.heise.de/rss/heise-atom.xml", "topic": "technology", "country": "DE", "site_domain": "heise.de"},
        {"key": "de_focus", "name": "Focus", "rss_url": "https://rss.focus.de/fol/XML/rss_folnews.xml", "topic": "general", "country": "DE", "site_domain": "focus.de"},
    ],
    "en": [
        {"key": "en_cbs", "name": "CBS News", "rss_url": "https://www.cbsnews.com/latest/rss/main", "topic": "general", "country": "US", "site_domain": "cbsnews.com"},
        {"key": "en_abcnews", "name": "ABC News", "rss_url": "https://abcnews.go.com/abcnews/topstories", "topic": "world", "country": "US", "site_domain": "abcnews.go.com"},
    ],
    "es": [
        {"key": "es_elperiodico", "name": "El Periodico", "rss_url": "https://www.elperiodico.com/es/rss/rss_portada.xml", "topic": "general", "country": "ES", "site_domain": "elperiodico.com"},
        {"key": "es_ondacero", "name": "Onda Cero", "rss_url": "https://www.ondacero.es/rss/noticias.xml", "topic": "politics", "country": "ES", "site_domain": "ondacero.es"},
    ],
    "fr": [
        {"key": "fr_bfmtv", "name": "BFMTV", "rss_url": "https://www.bfmtv.com/rss/news-24-7/", "topic": "general", "country": "FR", "site_domain": "bfmtv.com"},
        {"key": "fr_francetvinfo", "name": "Franceinfo", "rss_url": "https://www.francetvinfo.fr/titres.rss", "topic": "world", "country": "FR", "site_domain": "francetvinfo.fr"},
    ],
    "hi": [
        {"key": "hi_news18", "name": "News18 Hindi", "rss_url": "https://hindi.news18.com/commonfeeds/v1/hin/rss/india.xml", "topic": "general", "country": "IN", "site_domain": "news18.com"},
        {"key": "hi_nbt", "name": "Navbharat Times", "rss_url": "https://navbharattimes.indiatimes.com/rssfeedsdefault.cms", "topic": "culture", "country": "IN", "site_domain": "navbharattimes.indiatimes.com"},
    ],
    "it": [
        {"key": "it_ilfatto", "name": "Il Fatto Quotidiano", "rss_url": "https://www.ilfattoquotidiano.it/feed/", "topic": "politics", "country": "IT", "site_domain": "ilfattoquotidiano.it"},
        {"key": "it_ilgiornale", "name": "Il Giornale", "rss_url": "https://www.ilgiornale.it/rss.xml", "topic": "general", "country": "IT", "site_domain": "ilgiornale.it"},
    ],
    "ja": [
        {"key": "ja_itmedia", "name": "ITmedia", "rss_url": "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml", "topic": "technology", "country": "JP", "site_domain": "itmedia.co.jp"},
        {"key": "ja_fnn", "name": "FNN Prime", "rss_url": "https://www.fnn.jp/rss/news", "topic": "general", "country": "JP", "site_domain": "fnn.jp"},
    ],
    "ko": [
        {"key": "ko_mk", "name": "Maeil Business", "rss_url": "https://www.mk.co.kr/rss/30000001/", "topic": "business", "country": "KR", "site_domain": "mk.co.kr"},
        {"key": "ko_ytn", "name": "YTN", "rss_url": "https://www.ytn.co.kr/_ln/rss.xml", "topic": "general", "country": "KR", "site_domain": "ytn.co.kr"},
    ],
    "nl": [
        {"key": "nl_fd", "name": "FD", "rss_url": "https://fd.nl/rss.xml", "topic": "business", "country": "NL", "site_domain": "fd.nl"},
        {"key": "nl_metronieuws", "name": "Metro Nieuws", "rss_url": "https://www.metronieuws.nl/feed/", "topic": "general", "country": "NL", "site_domain": "metronieuws.nl"},
    ],
    "ro": [
        {"key": "ro_romanialibera", "name": "Romania Libera", "rss_url": "https://romanialibera.ro/feed/", "topic": "general", "country": "RO", "site_domain": "romanialibera.ro"},
        {"key": "ro_spotmedia", "name": "Spotmedia", "rss_url": "https://spotmedia.ro/feed", "topic": "politics", "country": "RO", "site_domain": "spotmedia.ro"},
    ],
    "ru": [
        {"key": "ru_mk", "name": "Moskovsky Komsomolets", "rss_url": "https://www.mk.ru/rss/index.xml", "topic": "general", "country": "RU", "site_domain": "mk.ru"},
        {"key": "ru_kp", "name": "Komsomolskaya Pravda", "rss_url": "https://www.kp.ru/rss/news/", "topic": "world", "country": "RU", "site_domain": "kp.ru"},
    ],
    "tr": [
        {"key": "tr_t24", "name": "T24", "rss_url": "https://t24.com.tr/rss", "topic": "general", "country": "TR", "site_domain": "t24.com.tr"},
        {"key": "tr_duvar", "name": "Gazete Duvar", "rss_url": "https://www.gazeteduvar.com.tr/export/rss", "topic": "politics", "country": "TR", "site_domain": "gazeteduvar.com.tr"},
    ],
    "vi": [
        {"key": "vi_vietnamplus", "name": "VietnamPlus", "rss_url": "https://www.vietnamplus.vn/rss/tin-moi-nhat.rss", "topic": "general", "country": "VN", "site_domain": "vietnamplus.vn"},
        {"key": "vi_baotintuc", "name": "Bao Tin Tuc", "rss_url": "https://baotintuc.vn/rss/tin-moi-nhat.rss", "topic": "world", "country": "VN", "site_domain": "baotintuc.vn"},
    ],
    "zh": [
        {"key": "zh_sina", "name": "Sina News", "rss_url": "https://rss.sina.com.cn/news/marquee/ddt.xml", "topic": "general", "country": "CN", "site_domain": "sina.com.cn"},
        {"key": "zh_qqnews", "name": "QQ News", "rss_url": "https://news.qq.com/rss_newsgn.htm", "topic": "technology", "country": "CN", "site_domain": "qq.com"},
    ],
}

TOPIC_CONFIGS = {
    "general": {"name": "General"},
    "world": {"name": "World"},
    "politics": {"name": "Politics"},
    "business": {"name": "Business"},
    "technology": {"name": "Technology"},
    "science": {"name": "Science"},
    "health": {"name": "Health"},
    "sports": {"name": "Sports"},
    "entertainment": {"name": "Entertainment"},
    "culture": {"name": "Culture"},
}

REGION_CONFIGS = {
    "global": {"name": "Global"},
    "europe": {"name": "Europe"},
    "asia": {"name": "Asia"},
    "oceania": {"name": "Oceania"},
    "middle_east": {"name": "Middle East"},
    "north_america": {"name": "North America"},
}

COUNTRY_CONFIGS = {
    "AU": {"name": "Australia", "region": "oceania"},
    "CA": {"name": "Canada", "region": "north_america"},
    "CH": {"name": "Switzerland", "region": "europe"},
    "EG": {"name": "Egypt", "region": "middle_east"},
    "AE": {"name": "United Arab Emirates", "region": "middle_east"},
    "DE": {"name": "Germany", "region": "europe"},
    "ES": {"name": "Spain", "region": "europe"},
    "FR": {"name": "France", "region": "europe"},
    "GB": {"name": "United Kingdom", "region": "europe"},
    "IN": {"name": "India", "region": "asia"},
    "IT": {"name": "Italy", "region": "europe"},
    "JP": {"name": "Japan", "region": "asia"},
    "KR": {"name": "South Korea", "region": "asia"},
    "NL": {"name": "Netherlands", "region": "europe"},
    "QA": {"name": "Qatar", "region": "middle_east"},
    "RO": {"name": "Romania", "region": "europe"},
    "RU": {"name": "Russia", "region": "europe"},
    "SA": {"name": "Saudi Arabia", "region": "middle_east"},
    "SG": {"name": "Singapore", "region": "asia"},
    "TR": {"name": "Turkey", "region": "europe"},
    "US": {"name": "United States", "region": "north_america"},
    "VN": {"name": "Vietnam", "region": "asia"},
    "CN": {"name": "China", "region": "asia"},
}

LANGUAGE_DEFAULT_COUNTRY = {
    "ar": "QA",
    "de": "DE",
    "en": "US",
    "es": "ES",
    "fr": "FR",
    "hi": "IN",
    "it": "IT",
    "ja": "JP",
    "ko": "KR",
    "nl": "NL",
    "ro": "RO",
    "ru": "RU",
    "tr": "TR",
    "vi": "VN",
    "zh": "CN",
}

SOURCE_COUNTRY_HINTS = {
    "aljazeera_world": "QA",
    "bbc_world": "GB",
    "cnn_world": "US",
    "dw_world": "DE",
    "fox_world": "US",
    "guardian_world": "GB",
    "npr_world": "US",
    "nyt_world": "US",
    "reuters_world": "US",
    "sky_world": "GB",
    "zh_zaobao": "SG",
}

GOOGLE_NEWS_LOCALE_HINTS = {
    "ar": {"hl": "ar", "gl": "SA", "ceid": "SA:ar"},
    "de": {"hl": "de", "gl": "DE", "ceid": "DE:de"},
    "en": {"hl": "en-US", "gl": "US", "ceid": "US:en"},
    "es": {"hl": "es", "gl": "ES", "ceid": "ES:es"},
    "fr": {"hl": "fr", "gl": "FR", "ceid": "FR:fr"},
    "hi": {"hl": "hi", "gl": "IN", "ceid": "IN:hi"},
    "it": {"hl": "it", "gl": "IT", "ceid": "IT:it"},
    "ja": {"hl": "ja", "gl": "JP", "ceid": "JP:ja"},
    "ko": {"hl": "ko", "gl": "KR", "ceid": "KR:ko"},
    "nl": {"hl": "nl", "gl": "NL", "ceid": "NL:nl"},
    "ro": {"hl": "ro", "gl": "RO", "ceid": "RO:ro"},
    "ru": {"hl": "ru", "gl": "RU", "ceid": "RU:ru"},
    "tr": {"hl": "tr", "gl": "TR", "ceid": "TR:tr"},
    "vi": {"hl": "vi", "gl": "VN", "ceid": "VN:vi"},
    "zh": {"hl": "zh-CN", "gl": "CN", "ceid": "CN:zh-Hans"},
}

TOPIC_QUERY_TERMS = {
    "ar": {
        "business": "اقتصاد",
        "culture": "ثقافة",
        "entertainment": "ترفيه",
        "general": "أخبار",
        "health": "صحة",
        "politics": "سياسة",
        "science": "علوم",
        "sports": "رياضة",
        "technology": "تقنية",
        "world": "العالم",
    },
    "de": {
        "business": "Wirtschaft",
        "culture": "Kultur",
        "entertainment": "Unterhaltung",
        "general": "Nachrichten",
        "health": "Gesundheit",
        "politics": "Politik",
        "science": "Wissenschaft",
        "sports": "Sport",
        "technology": "Technologie",
        "world": "Welt",
    },
    "en": {
        "business": "business",
        "culture": "culture",
        "entertainment": "entertainment",
        "general": "news",
        "health": "health",
        "politics": "politics",
        "science": "science",
        "sports": "sports",
        "technology": "technology",
        "world": "world",
    },
    "es": {
        "business": "economia",
        "culture": "cultura",
        "entertainment": "entretenimiento",
        "general": "noticias",
        "health": "salud",
        "politics": "politica",
        "science": "ciencia",
        "sports": "deportes",
        "technology": "tecnologia",
        "world": "mundo",
    },
    "fr": {
        "business": "economie",
        "culture": "culture",
        "entertainment": "divertissement",
        "general": "actualites",
        "health": "sante",
        "politics": "politique",
        "science": "science",
        "sports": "sport",
        "technology": "technologie",
        "world": "monde",
    },
    "hi": {
        "business": "बिजनेस",
        "culture": "संस्कृति",
        "entertainment": "मनोरंजन",
        "general": "समाचार",
        "health": "स्वास्थ्य",
        "politics": "राजनीति",
        "science": "विज्ञान",
        "sports": "खेल",
        "technology": "तकनीक",
        "world": "दुनिया",
    },
    "it": {
        "business": "economia",
        "culture": "cultura",
        "entertainment": "spettacoli",
        "general": "notizie",
        "health": "salute",
        "politics": "politica",
        "science": "scienza",
        "sports": "sport",
        "technology": "tecnologia",
        "world": "mondo",
    },
    "ja": {
        "business": "経済",
        "culture": "文化",
        "entertainment": "エンタメ",
        "general": "ニュース",
        "health": "健康",
        "politics": "政治",
        "science": "科学",
        "sports": "スポーツ",
        "technology": "テクノロジー",
        "world": "国際",
    },
    "ko": {
        "business": "경제",
        "culture": "문화",
        "entertainment": "연예",
        "general": "뉴스",
        "health": "건강",
        "politics": "정치",
        "science": "과학",
        "sports": "스포츠",
        "technology": "기술",
        "world": "국제",
    },
    "nl": {
        "business": "economie",
        "culture": "cultuur",
        "entertainment": "entertainment",
        "general": "nieuws",
        "health": "gezondheid",
        "politics": "politiek",
        "science": "wetenschap",
        "sports": "sport",
        "technology": "technologie",
        "world": "wereld",
    },
    "ro": {
        "business": "economie",
        "culture": "cultura",
        "entertainment": "divertisment",
        "general": "stiri",
        "health": "sanatate",
        "politics": "politica",
        "science": "stiinta",
        "sports": "sport",
        "technology": "tehnologie",
        "world": "international",
    },
    "ru": {
        "business": "экономика",
        "culture": "культура",
        "entertainment": "развлечения",
        "general": "новости",
        "health": "здоровье",
        "politics": "политика",
        "science": "наука",
        "sports": "спорт",
        "technology": "технологии",
        "world": "мир",
    },
    "tr": {
        "business": "ekonomi",
        "culture": "kultur sanat",
        "entertainment": "magazin",
        "general": "haber",
        "health": "saglik",
        "politics": "siyaset",
        "science": "bilim",
        "sports": "spor",
        "technology": "teknoloji",
        "world": "dunya",
    },
    "vi": {
        "business": "kinh doanh",
        "culture": "van hoa",
        "entertainment": "giai tri",
        "general": "tin tuc",
        "health": "suc khoe",
        "politics": "chinh tri",
        "science": "khoa hoc",
        "sports": "the thao",
        "technology": "cong nghe",
        "world": "the gioi",
    },
    "zh": {
        "business": "财经",
        "culture": "文化",
        "entertainment": "娱乐",
        "general": "新闻",
        "health": "健康",
        "politics": "政治",
        "science": "科学",
        "sports": "体育",
        "technology": "科技",
        "world": "国际",
    },
}

LANGUAGE_SOURCE_SEEDS = {
    "ar": [
        {"name": "Al Jazeera Arabic", "domain": "aljazeera.net", "country": "QA"},
        {"name": "Al Arabiya", "domain": "alarabiya.net", "country": "SA"},
        {"name": "Sky News Arabia", "domain": "skynewsarabia.com", "country": "AE"},
    ],
    "de": [
        {"name": "Tagesschau", "domain": "tagesschau.de", "country": "DE"},
        {"name": "Der Spiegel", "domain": "spiegel.de", "country": "DE"},
        {"name": "Die Welt", "domain": "welt.de", "country": "DE"},
    ],
    "en": [
        {"name": "BBC", "domain": "bbc.com", "country": "GB"},
        {"name": "Reuters", "domain": "reuters.com", "country": "US"},
        {"name": "The Guardian", "domain": "theguardian.com", "country": "GB"},
    ],
    "es": [
        {"name": "El Pais", "domain": "elpais.com", "country": "ES"},
        {"name": "El Mundo", "domain": "elmundo.es", "country": "ES"},
        {"name": "La Vanguardia", "domain": "lavanguardia.com", "country": "ES"},
    ],
    "fr": [
        {"name": "Le Monde", "domain": "lemonde.fr", "country": "FR"},
        {"name": "Le Figaro", "domain": "lefigaro.fr", "country": "FR"},
        {"name": "France24", "domain": "france24.com", "country": "FR"},
    ],
    "hi": [
        {"name": "Dainik Jagran", "domain": "jagran.com", "country": "IN"},
        {"name": "Aaj Tak", "domain": "aajtak.in", "country": "IN"},
        {"name": "NDTV India", "domain": "ndtv.in", "country": "IN"},
    ],
    "it": [
        {"name": "ANSA", "domain": "ansa.it", "country": "IT"},
        {"name": "La Repubblica", "domain": "repubblica.it", "country": "IT"},
        {"name": "Corriere della Sera", "domain": "corriere.it", "country": "IT"},
    ],
    "ja": [
        {"name": "NHK", "domain": "nhk.or.jp", "country": "JP"},
        {"name": "Asahi", "domain": "asahi.com", "country": "JP"},
        {"name": "Mainichi", "domain": "mainichi.jp", "country": "JP"},
    ],
    "ko": [
        {"name": "Yonhap", "domain": "yna.co.kr", "country": "KR"},
        {"name": "Hankyoreh", "domain": "hani.co.kr", "country": "KR"},
        {"name": "KBS", "domain": "kbs.co.kr", "country": "KR"},
    ],
    "nl": [
        {"name": "NOS", "domain": "nos.nl", "country": "NL"},
        {"name": "NU", "domain": "nu.nl", "country": "NL"},
        {"name": "de Volkskrant", "domain": "volkskrant.nl", "country": "NL"},
    ],
    "ro": [
        {"name": "HotNews", "domain": "hotnews.ro", "country": "RO"},
        {"name": "Digi24", "domain": "digi24.ro", "country": "RO"},
        {"name": "Adevarul", "domain": "adevarul.ro", "country": "RO"},
    ],
    "ru": [
        {"name": "TASS", "domain": "tass.ru", "country": "RU"},
        {"name": "RIA Novosti", "domain": "ria.ru", "country": "RU"},
        {"name": "Lenta", "domain": "lenta.ru", "country": "RU"},
    ],
    "tr": [
        {"name": "TRT Haber", "domain": "trthaber.com", "country": "TR"},
        {"name": "Hurriyet", "domain": "hurriyet.com.tr", "country": "TR"},
        {"name": "NTV", "domain": "ntv.com.tr", "country": "TR"},
    ],
    "vi": [
        {"name": "VNExpress", "domain": "vnexpress.net", "country": "VN"},
        {"name": "Tuoi Tre", "domain": "tuoitre.vn", "country": "VN"},
        {"name": "Dan Tri", "domain": "dantri.com.vn", "country": "VN"},
    ],
    "zh": [
        {"name": "Xinhua", "domain": "news.cn", "country": "CN"},
        {"name": "People CN", "domain": "people.com.cn", "country": "CN"},
        {"name": "China News", "domain": "chinanews.com.cn", "country": "CN"},
    ],
}

CATEGORY_TOPIC_KEYS = [
    "general",
    "world",
    "politics",
    "business",
    "technology",
    "science",
    "health",
    "sports",
    "entertainment",
    "culture",
]

LANGUAGE_TOPIC_DOMAIN_OVERRIDES = {
    "ar": {
        "business": {"name": "BBC Arabic", "domain": "bbc.com", "country": "QA"},
        "culture": {"name": "BBC Arabic", "domain": "bbc.com", "country": "QA"},
        "health": {"name": "BBC Arabic", "domain": "bbc.com", "country": "QA"},
        "sports": {"name": "CNN Arabic", "domain": "arabic.cnn.com", "country": "AE"},
        "technology": {"name": "BBC Arabic", "domain": "bbc.com", "country": "QA"},
        "world": {"name": "CNN Arabic", "domain": "arabic.cnn.com", "country": "AE"},
    },
    "de": {
        "world": {"name": "Die Welt", "domain": "welt.de", "country": "DE"},
    },
    "en": {
        "technology": {"name": "BBC", "domain": "bbc.com", "country": "GB"},
    },
    "fr": {
        "business": {"name": "Le Figaro", "domain": "lefigaro.fr", "country": "FR"},
        "health": {"name": "Le Figaro", "domain": "lefigaro.fr", "country": "FR"},
    },
    "hi": {
        "entertainment": {"name": "BBC Hindi", "domain": "bbc.com", "country": "IN"},
        "health": {"name": "BBC Hindi", "domain": "bbc.com", "country": "IN"},
        "politics": {"name": "Aaj Tak", "domain": "aajtak.in", "country": "IN"},
        "science": {"name": "BBC Hindi", "domain": "bbc.com", "country": "IN"},
        "technology": {"name": "BBC Hindi", "domain": "bbc.com", "country": "IN"},
    },
    "it": {
        "politics": {"name": "ANSA", "domain": "ansa.it", "country": "IT"},
    },
    "ja": {
        "world": {"name": "Mainichi", "domain": "mainichi.jp", "country": "JP"},
    },
    "nl": {
        "entertainment": {"name": "NOS", "domain": "nos.nl", "country": "NL"},
        "politics": {"name": "NOS", "domain": "nos.nl", "country": "NL"},
        "science": {"name": "NOS", "domain": "nos.nl", "country": "NL"},
        "sports": {"name": "NOS", "domain": "nos.nl", "country": "NL"},
        "technology": {"name": "Tweakers", "domain": "tweakers.net", "country": "NL"},
        "world": {"name": "NOS", "domain": "nos.nl", "country": "NL"},
    },
    "ru": {
        "business": {"name": "RIA Novosti", "domain": "ria.ru", "country": "RU"},
        "culture": {"name": "RIA Novosti", "domain": "ria.ru", "country": "RU"},
        "health": {"name": "Interfax", "domain": "interfax.ru", "country": "RU"},
        "politics": {"name": "RIA Novosti", "domain": "ria.ru", "country": "RU"},
        "world": {"name": "RIA Novosti", "domain": "ria.ru", "country": "RU"},
    },
}

GOOGLE_TOPIC_DISABLED_LANGUAGES = {"vi", "zh"}

ENABLE_GOOGLE_TOPIC_SOURCES = str(os.getenv("ENABLE_GOOGLE_TOPIC_SOURCES", "0") or "").strip().lower() in {
    "1",
    "true",
    "yes",
}
ENABLE_CURATED_TOPIC_SOURCES = str(os.getenv("ENABLE_CURATED_TOPIC_SOURCES", "1") or "").strip().lower() not in {
    "0",
    "false",
    "no",
}
CATEGORY_SOURCES_PER_TOPIC = max(1, int(os.getenv("CATEGORY_SOURCES_PER_TOPIC", "3")))


def slugify_key(text: str) -> str:
    raw = unescape(str(text or "")).replace("\xa0", " ")
    value = re.sub(r"\s+", " ", raw).strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def google_news_locale(language_key: str, country_key: str):
    hint = GOOGLE_NEWS_LOCALE_HINTS.get(language_key)
    if hint:
        return hint["hl"], hint["gl"], hint["ceid"]
    country = (country_key or "US").upper()
    return "en-US", country, f"{country}:en"


def topic_query_term(topic_key: str, language_key: str) -> str:
    lang_terms = TOPIC_QUERY_TERMS.get(language_key, TOPIC_QUERY_TERMS.get("en", {}))
    return lang_terms.get(topic_key, topic_key)


def build_google_news_rss_url(query: str, language_key: str, country_key: str) -> str:
    query = re.sub(r"\s+", " ", str(query or "")).strip()
    if not query:
        query = "news"
    hl, gl, ceid = google_news_locale(language_key, country_key)
    params = urlencode(
        {"q": query, "hl": hl, "gl": gl, "ceid": ceid},
        quote_via=quote_plus,
    )
    return f"https://news.google.com/rss/search?{params}"


def build_google_topic_source_extensions():
    extensions = {lang: [] for lang in LANGUAGE_CONFIGS.keys()}
    for language_key, seeds in LANGUAGE_SOURCE_SEEDS.items():
        if language_key in GOOGLE_TOPIC_DISABLED_LANGUAGES:
            continue
        if not seeds:
            continue
        for idx, topic_key in enumerate(CATEGORY_TOPIC_KEYS):
            seed = seeds[idx % len(seeds)]
            source_key = f"{language_key}_{slugify_key(seed['name'])}_{topic_key}_gn"
            topic_term = topic_query_term(topic_key, language_key)
            query = f"site:{seed['domain']} {topic_term}".strip()
            country = seed.get("country") or LANGUAGE_DEFAULT_COUNTRY.get(language_key, "US")
            extensions[language_key].append(
                {
                    "key": source_key,
                    "name": f"{seed['name']} {TOPIC_CONFIGS.get(topic_key, {}).get('name', topic_key.title())}",
                    "rss_url": build_google_news_rss_url(query, language_key, country),
                    "topic": topic_key,
                    "country": country,
                    "site_domain": seed["domain"],
                    "feed_source": "google_news",
                }
            )
    return extensions


GOOGLE_TOPIC_SOURCE_EXTENSIONS = build_google_topic_source_extensions()


def build_google_topic_source_overrides():
    extensions = {lang: [] for lang in LANGUAGE_CONFIGS.keys()}
    for language_key, topics in LANGUAGE_TOPIC_DOMAIN_OVERRIDES.items():
        if language_key in GOOGLE_TOPIC_DISABLED_LANGUAGES:
            continue
        for topic_key, seed in topics.items():
            country = seed.get("country") or LANGUAGE_DEFAULT_COUNTRY.get(language_key, "US")
            source_key = f"{language_key}_{slugify_key(seed['name'])}_{topic_key}_gnx"
            topic_term = topic_query_term(topic_key, language_key)
            query = f"site:{seed['domain']} {topic_term}".strip()
            extensions[language_key].append(
                {
                    "key": source_key,
                    "name": f"{seed['name']} {TOPIC_CONFIGS.get(topic_key, {}).get('name', topic_key.title())}",
                    "rss_url": build_google_news_rss_url(query, language_key, country),
                    "topic": topic_key,
                    "country": country,
                    "site_domain": seed["domain"],
                    "feed_source": "google_news_override",
                }
            )
    return extensions


GOOGLE_TOPIC_SOURCE_OVERRIDES = build_google_topic_source_overrides()


def build_curated_topic_sources():
    def norm(value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()

    def infer_candidate_topic(source: dict) -> str:
        explicit = norm(source.get("topic", "")).lower()
        if explicit in TOPIC_CONFIGS:
            return explicit
        source_text = " ".join(
            [
                norm(source.get("key", "")).lower(),
                norm(source.get("name", "")).lower(),
                norm(source.get("rss_url", "")).lower(),
            ]
        )
        if re.search(r"\b(sport|spor|football|soccer|basket|tennis)\b", source_text):
            return "sports"
        if "world" in source_text:
            return "world"
        if re.search(r"\b(politic|siyaset|politique|politik|politica|полит|政治)\b", source_text):
            return "politics"
        if re.search(r"\b(business|econom|finance|ekonomi|wirtschaft|economia|finanza|эконом|财经)\b", source_text):
            return "business"
        if re.search(r"\b(tech|technology|teknoloji|technologie|tecnologia|технолог|科技)\b", source_text):
            return "technology"
        if re.search(r"\b(science|bilim|wissenschaft|ciencia|scienza|наука|科学)\b", source_text):
            return "science"
        if re.search(r"\b(health|sağlık|saglik|sante|gesundheit|salud|salute|здоров|健康)\b", source_text):
            return "health"
        if re.search(r"\b(entertainment|magazin|show|celeb|娱乐|연예|मनोरंजन)\b", source_text):
            return "entertainment"
        if re.search(r"\b(culture|kultur|kültür|cultura|文化|культура)\b", source_text):
            return "culture"
        return "general"

    def topic_affinity(source_topic: str, target_topic: str) -> int:
        if source_topic == target_topic:
            return 3
        if source_topic == "general":
            return 2
        if target_topic == "general":
            return 1
        return 0

    extensions = {lang: [] for lang in LANGUAGE_CONFIGS.keys()}
    for language_key in LANGUAGE_CONFIGS.keys():
        candidates = []
        seen_keys = set()
        for source in list(TOP_NEWS_SOURCES.get(language_key, [])) + list(
            TOPICAL_SOURCE_EXTENSIONS.get(language_key, [])
        ):
            source_key = norm(source.get("key", ""))
            if not source_key or source_key in seen_keys:
                continue
            seen_keys.add(source_key)
            candidates.append(source)

        if not candidates:
            continue

        source_topics = {norm(source.get("key", "")): infer_candidate_topic(source) for source in candidates}
        topic_index = {topic: idx for idx, topic in enumerate(CATEGORY_TOPIC_KEYS)}

        for topic_key in CATEGORY_TOPIC_KEYS:
            ranked = []
            for source in candidates:
                source_key = norm(source.get("key", ""))
                source_topic = source_topics.get(source_key, "general")
                affinity = topic_affinity(source_topic, topic_key)
                rotation_rank = (abs(hash(f"{language_key}:{topic_key}:{source_key}")) + topic_index[topic_key]) % 997
                ranked.append((affinity, rotation_rank, source))

            ranked.sort(key=lambda row: (row[0], -row[1]), reverse=True)
            chosen = []
            used_rss = set()
            used_keys = set()
            for _, _, source in ranked:
                source_key = norm(source.get("key", ""))
                rss_url = norm(source.get("rss_url", ""))
                if not source_key or not rss_url:
                    continue
                if source_key in used_keys or rss_url in used_rss:
                    continue
                used_keys.add(source_key)
                used_rss.add(rss_url)
                chosen.append(source)
                if len(chosen) >= CATEGORY_SOURCES_PER_TOPIC:
                    break

            for idx, source in enumerate(chosen, start=1):
                country = source.get("country") or LANGUAGE_DEFAULT_COUNTRY.get(language_key, "US")
                base_key = norm(source.get("key", ""))
                source_key = f"{base_key}_{topic_key}_cur{idx}"
                extensions[language_key].append(
                    {
                        "key": source_key,
                        "name": source["name"],
                        "rss_url": source["rss_url"],
                        "topic": topic_key,
                        "country": country,
                        "feed_source": "curated_direct",
                    }
                )
                if source.get("rss_urls"):
                    extensions[language_key][-1]["rss_urls"] = list(source["rss_urls"])
    return extensions


CURATED_TOPIC_SOURCES = build_curated_topic_sources()

ENABLE_SOURCE_QUALITY_GATE = str(os.getenv("ENABLE_SOURCE_QUALITY_GATE", "1") or "").strip().lower() not in {
    "0",
    "false",
    "no",
}
ENABLE_DYNAMIC_QUALITY_GATE = str(os.getenv("ENABLE_DYNAMIC_QUALITY_GATE", "0") or "").strip().lower() in {
    "1",
    "true",
    "yes",
}

QUALITY_GATED_SOURCE_KEYS = {
    "ar_aawsat",
    "ar_al_arabiya_sports_gn",
    "ar_al_arabiya_world_gn",
    "ar_al_jazeera_arabic_business_gn",
    "ar_al_jazeera_arabic_culture_gn",
    "ar_al_jazeera_arabic_general_gn",
    "ar_al_jazeera_arabic_health_gn",
    "ar_aljazeera",
    "ar_rt",
    "ar_skynewsarabia",
    "de_bild",
    "de_der_spiegel_world_gn",
    "de_dlf",
    "de_spiegel",
    "de_tagesschau_general_gn",
    "dw_world",
    "en_reuters_sports_gn",
    "en_reuters_technology_gn",
    "en_reuters_world_gn",
    "es_el_pais_general_gn",
    "es_elconfidencial",
    "es_marca",
    "fr_le_monde_business_gn",
    "fr_france24",
    "fr_le_monde_general_gn",
    "fr_le_monde_health_gn",
    "fr_liberation",
    "fr_ouestfrance",
    "hi_aaj_tak_technology_gn",
    "hi_dainik_jagran_health_gn",
    "hi_indiatv",
    "hi_ndtv_india_entertainment_gn",
    "hi_ndtv_india_politics_gn",
    "hi_ndtv_india_science_gn",
    "hi_ndtvindia",
    "it_corriere_della_sera_politics_gn",
    "it_fanpage",
    "it_lastampa",
    "ja_asahi",
    "ja_asahi_world_gn",
    "ja_47news",
    "ja_jiji",
    "ja_sankei",
    "ja_tbs",
    "ja_tokyo",
    "ja_yomiuri",
    "ko_chosun",
    "ko_donga",
    "ko_khan",
    "nl_ad",
    "nl_de_volkskrant_entertainment_gn",
    "nl_de_volkskrant_politics_gn",
    "nl_de_volkskrant_science_gn",
    "nl_nu",
    "nl_nu_sports_gn",
    "nl_nu_technology_gn",
    "nl_nu_world_gn",
    "nl_parool",
    "nl_rtl",
    "nl_telegraaf",
    "nl_trouw",
    "nl_volkskrant",
    "npr_world",
    "reuters_world",
    "ro_antena3",
    "ro_mediafax",
    "ro_ziare",
    "ru_gazeta",
    "ru_iz",
    "ru_kommersant",
    "ru_lenta_politics_gn",
    "ru_rg",
    "ru_ria_novosti_world_gn",
    "ru_tass",
    "ru_tass_business_gn",
    "ru_tass_culture_gn",
    "ru_tass_general_gn",
    "ru_tass_health_gn",
    "tr_ntvspor",
    "tr_sozcu",
    "vi_nld",
    "vi_vnexpress",
    "vi_tuoi_tre_technology_gn",
    "vi_vov",
    "vi_vtc",
    "zh_cctv",
    "zh_china_news_entertainment_gn",
    "zh_china_news_science_gn",
    "zh_huanqiu",
    "zh_ifeng",
    "zh_sohu",
    "zh_xinhua_business_gn",
    "zh_xinhua_culture_gn",
    "zh_zaobao",
    "ar_alarabiya",
    "ar_al_arabiya_technology_gn",
    "ar_bbc_arabic_world_gnx",
    "de_tagesschau_world_gnx",
    "es_abc",
    "hi_aaj_tak_technology_gnx",
    "nl_nos_technology_gnx",
    "ru_ria",
    "ru_ria_novosti_health_gnx",
    "es_publico",
    "es_rtve",
    "fr_leparisien",
    "hi_jagran",
    "hi_livehindustan",
    "hi_zee",
    "it_adnkronos",
    "it_rainews",
    "ja_mainichi",
    "ja_mainichi_business_dalias",
    "ja_mainichi_culture_dalias",
    "ja_mainichi_entertainment_dalias",
    "ja_mainichi_general_dalias",
    "ja_mainichi_health_dalias",
    "ja_mainichi_politics_dalias",
    "ja_mainichi_science_dalias",
    "ja_mainichi_sports_dalias",
    "ja_mainichi_technology_dalias",
    "ja_mainichi_world_dalias",
    "ja_nikkei",
    "ko_joongang",
    "ko_kbs",
    "ko_mbc",
    "ko_seoul",
    "ko_yonhap",
    "ko_yonhap_business_dalias",
    "ko_yonhap_culture_dalias",
    "ko_yonhap_entertainment_dalias",
    "ko_yonhap_general_dalias",
    "ko_yonhap_health_dalias",
    "ko_yonhap_politics_dalias",
    "ko_yonhap_science_dalias",
    "ko_yonhap_sports_dalias",
    "ko_yonhap_technology_dalias",
    "ko_yonhap_world_dalias",
    "nl_bnr",
    "ro_euronews",
    "vi_vietnamnet",
    "vi_znews",
    "zh_chinanews",
    "zh_chinanews_business_alias",
    "zh_chinanews_culture_alias",
    "zh_chinanews_entertainment_alias",
    "zh_chinanews_health_alias",
    "zh_chinanews_politics_alias",
    "zh_chinanews_science_alias",
    "zh_chinanews_sports_alias",
    "zh_stcn",
}


def load_dynamic_quality_gated_keys():
    if not ENABLE_SOURCE_QUALITY_GATE or not ENABLE_DYNAMIC_QUALITY_GATE:
        return set()

    env_path = str(os.getenv("SOURCE_QUALITY_REPORT_PATH", "") or "").strip()
    candidate_paths = []
    if env_path:
        candidate_paths.append(env_path)

    report_dirs = [
        os.path.join(BASE_DIR, "source_validation_reports"),
        os.path.join(PROJECT_ROOT, "evaluation", "source_validation_reports"),
    ]
    for report_dir in report_dirs:
        if not os.path.isdir(report_dir):
            continue
        json_files = [
            os.path.join(report_dir, name)
            for name in os.listdir(report_dir)
            if name.startswith("source_validation_") and name.endswith(".json")
        ]
        if json_files:
            latest = max(json_files, key=lambda p: os.path.getmtime(p))
            if latest not in candidate_paths:
                candidate_paths.append(latest)

    for path in candidate_paths:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
            results = payload.get("results") or []
            failed = {
                str(row.get("source_key", "") or "").strip()
                for row in results
                if isinstance(row, dict) and not row.get("pass")
            }
            failed.discard("")
            if failed:
                return failed
        except Exception:
            continue
    return set()


DYNAMIC_QUALITY_GATED_KEYS = load_dynamic_quality_gated_keys()


def infer_topic(source_key: str, source_cfg: dict) -> str:
    explicit = re.sub(r"\s+", " ", str(source_cfg.get("topic", "") or "")).strip().lower()
    if explicit in TOPIC_CONFIGS:
        return explicit

    source_text = " ".join(
        [
            re.sub(r"\s+", " ", str(source_key or "")).strip().lower(),
            re.sub(r"\s+", " ", str(source_cfg.get("name", "") or "")).strip().lower(),
            re.sub(r"\s+", " ", str(source_cfg.get("rss_url", "") or "")).strip().lower(),
        ]
    )
    if re.search(r"\b(sport|spor|football|soccer|basket|tennis)\b", source_text):
        return "sports"
    if "world" in source_text:
        return "world"
    if re.search(r"\b(politic|siyaset|politique|politik|politica|полит|政治)\b", source_text):
        return "politics"
    if re.search(r"\b(business|econom|finance|ekonomi|wirtschaft|economia|finanza|эконом|财经)\b", source_text):
        return "business"
    if re.search(r"\b(tech|technology|teknoloji|technologie|tecnologia|технолог|科技)\b", source_text):
        return "technology"
    if re.search(r"\b(science|bilim|wissenschaft|ciencia|scienza|наука|科学)\b", source_text):
        return "science"
    if re.search(r"\b(health|sağlık|saglik|sante|gesundheit|salud|salute|здоров|健康)\b", source_text):
        return "health"
    if re.search(r"\b(entertainment|magazin|show|celeb|娱乐|연예|मनोरंजन)\b", source_text):
        return "entertainment"
    if re.search(r"\b(culture|kultur|kültür|kultur|cultura|文化|культура)\b", source_text):
        return "culture"
    return "general"


def infer_country(language_key: str, source_key: str, source_cfg: dict) -> str:
    explicit = re.sub(r"\s+", " ", str(source_cfg.get("country", "") or "")).strip().upper()
    if explicit in COUNTRY_CONFIGS:
        return explicit
    if source_key in SOURCE_COUNTRY_HINTS:
        return SOURCE_COUNTRY_HINTS[source_key]
    return LANGUAGE_DEFAULT_COUNTRY.get(language_key, "US")


def infer_region(country_key: str, source_cfg: dict) -> str:
    explicit = re.sub(r"\s+", " ", str(source_cfg.get("region", "") or "")).strip().lower()
    if explicit in REGION_CONFIGS:
        return explicit
    return COUNTRY_CONFIGS.get(country_key, {}).get("region", "global")


def source_site_key(source_cfg: dict) -> str:
    site_domain = re.sub(r"\s+", " ", str(source_cfg.get("site_domain", "") or "")).strip().lower()
    if site_domain:
        return re.sub(r"^www\d*\.", "", site_domain)

    rss_candidates = list(source_cfg.get("rss_urls") or [])
    if source_cfg.get("rss_url"):
        rss_candidates.insert(0, source_cfg.get("rss_url"))
    for rss_url in rss_candidates:
        host = re.sub(r"\s+", " ", str(urlparse(str(rss_url or "")).netloc or "")).strip().lower()
        host = re.sub(r"^www\d*\.", "", host)
        if host:
            return host
    return ""


def build_news_sources():
    built = {}
    for lang_key, source_list in TOP_NEWS_SOURCES.items():
        merged_sources = (
            list(source_list)
            + TOPICAL_SOURCE_EXTENSIONS.get(lang_key, [])
            + UNIQUE_SOURCE_EXTENSIONS.get(lang_key, [])
            + (GOOGLE_TOPIC_SOURCE_EXTENSIONS.get(lang_key, []) if ENABLE_GOOGLE_TOPIC_SOURCES else [])
            + (GOOGLE_TOPIC_SOURCE_OVERRIDES.get(lang_key, []) if ENABLE_GOOGLE_TOPIC_SOURCES else [])
            + (CURATED_TOPIC_SOURCES.get(lang_key, []) if ENABLE_CURATED_TOPIC_SOURCES else [])
        )
        grouped_by_site = {}
        for source in merged_sources:
            source_key = source.get("key", "")
            if ENABLE_SOURCE_QUALITY_GATE and (
                source_key in QUALITY_GATED_SOURCE_KEYS or source_key in DYNAMIC_QUALITY_GATED_KEYS
            ):
                continue
            site_key = source_site_key(source) or f"{lang_key}:{source_key}"
            grouped_by_site.setdefault(site_key, []).append(source)

        for _, group in grouped_by_site.items():
            group = sorted(
                group,
                key=lambda src: (
                    0 if not src.get("feed_source") else 1,
                    0 if src.get("topic") == "general" else 1,
                    len(str(src.get("key", ""))),
                ),
            )
            source = group[0]
            source_key = source["key"]
            if source_key in built:
                continue

            country = infer_country(lang_key, source_key, source)
            group_topics = {infer_topic(src.get("key", ""), src) for src in group}
            topic = "general" if len(group_topics) > 1 else infer_topic(source_key, source)
            region = infer_region(country, source)

            built[source_key] = {
                "name": source["name"],
                "rss_url": source["rss_url"],
                "language": lang_key,
                "topic": topic,
                "country": country,
                "region": region,
            }
            if source.get("rss_urls"):
                built[source_key]["rss_urls"] = list(source["rss_urls"])
            site_domain = source_site_key(source)
            if site_domain:
                built[source_key]["site_domain"] = site_domain
            if source.get("feed_source"):
                built[source_key]["feed_source"] = source["feed_source"]
    return built


NEWS_SOURCES = build_news_sources()


def normalize_text(text: str) -> str:
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
    value = str(text or "")
    for _ in range(max(1, rounds)):
        decoded = unescape(value)
        if decoded == value:
            break
        value = decoded
    return value


def mojibake_count(text: str) -> int:
    text = str(text or "")
    marker_hits = sum(text.count(marker) for marker in MOJIBAKE_MARKERS)
    marker_hits += sum(text.count(marker) for marker in COMMON_UTF8_MOJIBAKE_SEQUENCES)
    marker_hits += len(re.findall(r"[\u00c2\u00c3\u00e2\u00e3][\u0080-\u00bf]", text))
    marker_hits += len(re.findall(r"[\u00e4-\u00e9][\u0080-\u00bf]{2,}", text))
    return marker_hits


def repair_mojibake(text: str) -> str:
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
    text = recursive_unescape(text)
    text = repair_mojibake(text)
    text = text.replace("\u200b", " ")
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]", " ", text)
    return normalize_text(text)


SENTENCE_BOUNDARY_PATTERN = re.compile(r"(?<=[.!?…。！？؟])\s*")
CJK_CHAR_PATTERN = re.compile(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7a3]")


def split_sentences(text: str):
    text = normalize_extracted_text(text)
    if not text:
        return []
    parts = [part.strip() for part in SENTENCE_BOUNDARY_PATTERN.split(text) if part.strip()]
    return parts if parts else [text]


def cjk_char_count(text: str) -> int:
    return len(CJK_CHAR_PATTERN.findall(text or ""))


def word_like_count(text: str) -> int:
    text = normalize_extracted_text(text)
    if not text:
        return 0
    latin_like_words = re.findall(r"\b[\w'-]+\b", text)
    cjk_units = cjk_char_count(text) // 2
    return max(len(latin_like_words), cjk_units)


def looks_like_code_noise(text: str) -> bool:
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
    match = re.search(r"charset\s*=\s*([A-Za-z0-9._-]+)", content_type or "", flags=re.IGNORECASE)
    return (match.group(1) if match else "").strip()


def _extract_meta_charset(raw_bytes: bytes) -> str:
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
    return {t for t in re.findall(r"\b[\w'-]+\b", (text or "").lower()) if len(t) > 2}


def is_near_duplicate_text(a: str, b: str, threshold: float = 0.82) -> bool:
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
    cleaned = normalize_extracted_text(text)
    if not cleaned:
        return ""
    for pattern in _source_cleanup_patterns(source_key, source_url):
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,-|")
    return cleaned


def strip_leading_metadata_prefix(text: str) -> str:
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


def postprocess_summary(summary: str, title: str, language_key: str) -> str:
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


def strip_html(text: str) -> str:
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", text)
    return normalize_extracted_text(clean)


def _sanitize_html_fragment(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return normalize_extracted_text(text)


def _decode_json_escaped_value(raw_value: str) -> str:
    raw_value = str(raw_value or "")
    if not raw_value:
        return ""
    try:
        decoded = json.loads(f'"{raw_value}"')
    except Exception:
        decoded = raw_value.replace("\\n", " ").replace("\\t", " ").replace('\\"', '"')
    return normalize_extracted_text(decoded)


def _iter_article_bodies_from_json(node):
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
    links = re.findall(r"(?is)<a\b[^>]*>(.*?)</a>", paragraph_html or "")
    if not links:
        return False
    link_text = normalize_extracted_text(" ".join(_sanitize_html_fragment(link) for link in links))
    if not link_text:
        return False
    return len(link_text) / max(1, len(paragraph_text)) > 0.72 and len(paragraph_text) < 420


def extract_paragraphs_from_html_block(html_block: str, min_chars: int = 40):
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


def extractive_fallback(text: str, max_chars: int = 280, avoid_text: str = "") -> str:
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


def has_sentence_ending(text: str) -> bool:
    text = normalize_text(text)
    if not text:
        return False
    return bool(re.search(r"[.!?…][\"')\]]*$", text)) or text.endswith(("。", "؟", "！", "؟", "…"))


def finalize_summary_text(summary: str, source_text: str) -> str:
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


def _local_name(tag: str) -> str:
    if not tag:
        return ""
    return tag.rsplit("}", 1)[-1].lower()


def find_child_text_anyns(item: ET.Element, name_candidates):
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
    if not fragment:
        return ""
    m = re.search(r'(?is)<img[^>]+src=["\']([^"\']+)["\']', fragment)
    if not m:
        return ""
    return normalize_text(m.group(1))


def extract_image_url_from_rss_item(item: ET.Element, description: str) -> str:
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


@lru_cache(maxsize=1)
def load_translator():
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


class nullcontext:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def normalize_filter_value(value: str) -> str:
    normalized = normalize_text(value).lower()
    if normalized in {"", "__all__", "all"}:
        return ""
    return normalized


def filter_sources(
    language_key: str,
    topic_key: str = "",
    country_key: str = "",
    region_key: str = "",
):
    topic_key = normalize_filter_value(topic_key)
    country_key = normalize_filter_value(country_key).upper()
    region_key = normalize_filter_value(region_key)
    filtered = {}
    for key, source in NEWS_SOURCES.items():
        if source.get("language") != language_key:
            continue
        if topic_key and source.get("topic") != topic_key:
            continue
        if country_key and (source.get("country") or "").upper() != country_key:
            continue
        if region_key and source.get("region") != region_key:
            continue
        filtered[key] = source
    return filtered


def gather_news(
    limit_per_source: int,
    language_key: str,
    selected_sources: list,
    topic_key: str = "",
    country_key: str = "",
    region_key: str = "",
):
    lang_sources = filter_sources(
        language_key=language_key,
        topic_key=topic_key,
        country_key=country_key,
        region_key=region_key,
    )
    if selected_sources:
        keys = [k for k in selected_sources if k in lang_sources]
        if not keys:
            return []
    else:
        keys = list(lang_sources.keys())

    all_entries = []

    raw_limit = max(1, limit_per_source * max(1, SOURCE_OVERSAMPLE_FACTOR))
    for key in keys:
        cfg = lang_sources[key]
        all_entries.extend(fetch_source_news(key, cfg, raw_limit))

    all_entries.sort(
        key=lambda x: x["published_at"] or datetime.fromtimestamp(0, tz=timezone.utc),
        reverse=True,
    )
    return all_entries
