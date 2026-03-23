import os
import re
import hashlib
from collections import OrderedDict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from functools import lru_cache
from html import unescape
from threading import Lock
from urllib.parse import unquote, urlparse
from urllib.error import URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

from flask import Flask, jsonify, render_template, request

try:
    import requests
except ImportError:
    requests = None

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
        {"key": "tr_milliyet", "name": "Milliyet", "rss_url": "https://www.milliyet.com.tr/rss/rssnew/gundemr.xml"},
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

TOPIC_CONFIGS = {
    "general": {"name": "General"},
    "world": {"name": "World"},
    "sports": {"name": "Sports"},
}

REGION_CONFIGS = {
    "global": {"name": "Global"},
    "europe": {"name": "Europe"},
    "asia": {"name": "Asia"},
    "middle_east": {"name": "Middle East"},
    "north_america": {"name": "North America"},
}

COUNTRY_CONFIGS = {
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


def build_news_sources():
    built = {}
    for lang_key, source_list in TOP_NEWS_SOURCES.items():
        merged_sources = list(source_list) + TOPICAL_SOURCE_EXTENSIONS.get(lang_key, [])
        for source in merged_sources:
            source_key = source["key"]
            if source_key in built:
                continue
            country = infer_country(lang_key, source_key, source)
            topic = infer_topic(source_key, source)
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
    return built


NEWS_SOURCES = build_news_sources()


def normalize_text(text: str) -> str:
    text = unescape(text or "")
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


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


def clean_article_for_summarization(text: str, language_key: str, title: str = "") -> str:
    text = normalize_text(text)
    if not text:
        return ""

    if language_key == "tr":
        # Remove common Turkish news metadata fragments that hurt summary quality.
        patterns = [
            r"\bGiriş Tarihi\s*:\s*[^.]{1,80}",
            r"\bSon Güncelleme\s*:\s*[^.]{1,80}",
            r"\bYayınlanma Tarihi\s*:\s*[^.]{1,80}",
            r"\bGüncelleme Tarihi\s*:\s*[^.]{1,80}",
            r"\b[0-3]?\d\.[0-1]?\d\.\d{4}\s+[0-2]?\d:[0-5]\d\b",
            r"\bFoto(?:ğraf|graf)\s*:\s*[^.]{1,100}",
            r"\bKaynak\s*:\s*[^.]{1,100}",
        ]
        for pattern in patterns:
            text = re.sub(pattern, " ", text, flags=re.IGNORECASE)

    # Many pages repeat the exact headline at the start of the article body.
    # Remove leading sentence(s) that are near-duplicates of the title.
    if title:
        parts = re.split(r"(?<=[.!?])\s+", text)
        while parts and is_near_duplicate_text(parts[0], title):
            parts = parts[1:]
        if parts:
            text = " ".join(parts)

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

    return clean_article_for_summarization(summary, language_key, title=title)


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

    # 1) JSON-LD articleBody is often the cleanest extraction path for modern sites.
    json_ld_bodies = re.findall(
        r'(?is)"articleBody"\s*:\s*"((?:\\.|[^"\\]){140,})"', cleaned
    )
    if json_ld_bodies:
        json_ld_texts = [normalize_text(bytes(x, "utf-8").decode("unicode_escape")) for x in json_ld_bodies]
        json_ld_texts = [t for t in json_ld_texts if len(t) >= 140]
        if json_ld_texts:
            return max(json_ld_texts, key=len)[:MAX_ARTICLE_CHARS]

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
        if len(best) >= min(MIN_ARTICLE_CHARS, 220):
            return best[:MAX_ARTICLE_CHARS]

    # 2) Many news sites keep body text in div/section/main containers.
    content_blocks = re.findall(
        r'(?is)<(?:div|section|main)\b[^>]*(?:id|class)\s*=\s*["\'][^"\']*(?:article|content|story|post|body)[^"\']*["\'][^>]*>(.*?)</(?:div|section|main)>',
        cleaned,
    )
    for block in content_blocks:
        block_paragraphs = [
            _sanitize_html_fragment(p)
            for p in re.findall(r"(?is)<p\b[^>]*>(.*?)</p>", block)
        ]
        block_paragraphs = [p for p in block_paragraphs if len(p) >= 40]
        if block_paragraphs:
            joined = " ".join(block_paragraphs)
            if len(joined) >= 140:
                return joined[:MAX_ARTICLE_CHARS]

    paragraphs = [
        _sanitize_html_fragment(p) for p in re.findall(r"(?is)<p\b[^>]*>(.*?)</p>", cleaned)
    ]
    filtered = []
    for p in paragraphs:
        if len(p) < 40:
            continue
        low = p.lower()
        if "cookie" in low and "consent" in low:
            continue
        if "subscribe" in low and "newsletter" in low:
            continue
        filtered.append(p)

    if filtered:
        combined = " ".join(filtered)
        if len(combined) >= 140:
            return combined[:MAX_ARTICLE_CHARS]

    # 3) Last resort: plain body text (can be noisy but better than empty).
    body_match = re.search(r"(?is)<body\b[^>]*>(.*?)</body>", cleaned)
    if body_match:
        body_text = _sanitize_html_fragment(body_match.group(1))
        body_text = re.sub(
            r"\b(sign in|subscribe|cookie|accept all|advertisement|privacy policy)\b",
            " ",
            body_text,
            flags=re.I,
        )
        body_text = normalize_text(body_text)
        if len(body_text) >= 220:
            return body_text[:MAX_ARTICLE_CHARS]
    return ""


@lru_cache(maxsize=256)
def fetch_article_text(url: str) -> str:
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
                html_text = response.text[: MAX_ARTICLE_CHARS * 3]
        except Exception:
            html_text = ""

    if not html_text:
        try:
            req = Request(resolved_url, headers=headers)
            with urlopen(req, timeout=ARTICLE_FETCH_TIMEOUT) as response:
                content_type = (response.headers.get("Content-Type") or "").lower()
                if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                    return ""
                html_bytes = response.read(MAX_ARTICLE_CHARS * 3)
                html_text = html_bytes.decode("utf-8", errors="ignore")
        except Exception:
            html_text = ""

    extracted = extract_article_text(html_text) if html_text else ""
    if extracted:
        return extracted

    # Robust fallback extractor for JS-heavy/complex templates.
    if trafilatura is not None:
        try:
            downloaded = trafilatura.fetch_url(resolved_url)
            if downloaded:
                text = trafilatura.extract(
                    downloaded,
                    include_comments=False,
                    include_tables=False,
                    favor_recall=True,
                )
                text = normalize_text(text or "")
                if len(text) >= 140:
                    return text[:MAX_ARTICLE_CHARS]
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
                html_text = response.text[: MAX_ARTICLE_CHARS * 2]
        except Exception:
            html_text = ""
    if not html_text:
        return ""
    return extract_image_from_html(html_text)


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
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text) if p.strip()]
    usable_parts = [p for p in parts if not (avoid_text and is_near_duplicate_text(p, avoid_text))]
    parts = usable_parts if usable_parts else parts
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
            app.logger.warning(
                "rss_fetch_error source=%s url=%s error=%s",
                source_key,
                rss_url,
                str(exc)[:180],
            )
            continue
        except Exception as exc:
            app.logger.warning(
                "rss_fetch_error source=%s url=%s error=%s",
                source_key,
                rss_url,
                str(exc)[:180],
            )
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
        topics=TOPIC_CONFIGS,
        countries=COUNTRY_CONFIGS,
        regions=REGION_CONFIGS,
        models=MODEL_PATHS,
        default_model=DEFAULT_MODEL_KEY,
        default_language=default_language,
    )


@app.get("/api/news")
def api_news():
    limit = int(request.args.get("limit", 2))
    source = request.args.get("source", "")
    language = request.args.get("language", DEFAULT_LANGUAGE_KEY)
    output_language = request.args.get("output_language", language)
    model_key = request.args.get("model", DEFAULT_MODEL_KEY)
    sources_param = request.args.get("sources", "")
    topic = request.args.get("topic", "")
    country = request.args.get("country", "")
    region = request.args.get("region", "")
    include_raw = request.args.get("include_raw", "false").lower() == "true"
    translation_model_active = bool((TRANSLATION_MODEL_REF or "").strip())

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

    if output_language not in LANGUAGE_CONFIGS:
        return (
            jsonify(
                {
                    "error": "Invalid output language key",
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

    limit_per_source = max(1, min(limit, 15))
    entries = gather_news(
        limit_per_source=limit_per_source,
        language_key=language,
        selected_sources=selected_sources,
        topic_key=topic,
        country_key=country,
        region_key=region,
    )
    result = []
    source_type_counts = {"article": 0, "rss": 0}
    skipped_due_to_missing_article = 0
    produced_per_source = {}
    for item in entries:
        source_key = item["source_key"]
        current_count = produced_per_source.get(source_key, 0)
        if current_count >= limit_per_source:
            continue

        article_text = fetch_article_text(item["link"])
        if not article_text:
            skipped_due_to_missing_article += 1
            app.logger.info(
                "article_fetch_skip source=%s link=%s",
                item["source_name"],
                item["link"][:180],
            )
            continue

        article_text = clean_article_for_summarization(
            article_text, language, title=item["title"]
        )
        if not article_text:
            skipped_due_to_missing_article += 1
            continue

        text_for_summary = article_text
        summary_input_type = "article"
        summary = summarize_article_cached(
            text_for_summary,
            model_key,
            language,
            article_key=item.get("link", ""),
        )
        summary = postprocess_summary(summary, item["title"], language)
        if not summary:
            summary = normalize_text(
                extractive_fallback(text_for_summary, avoid_text=item["title"])
            )

        title_out = item["title"]
        summary_out = summary
        translation_applied = False
        if output_language != language:
            title_out = translate_text(item["title"], language, output_language)
            summary_out = translate_text(summary, language, output_language)
            translation_applied = bool(title_out != item["title"] or summary_out != summary)

        image_url = item.get("image_url") or fetch_article_image(item["link"])
        source_type_counts[summary_input_type] = source_type_counts.get(summary_input_type, 0) + 1
        produced_per_source[source_key] = current_count + 1
        app.logger.info(
            "summary_input_type=%s source=%s title=%s",
            summary_input_type,
            item["source_name"],
            item["title"][:100],
        )
        result.append(
            {
                "title": title_out,
                "summary": summary_out,
                "source_name": item["source_name"],
                "source_key": item["source_key"],
                "link": item["link"],
                "published_at": (
                    item["published_at"].isoformat() if item["published_at"] else None
                ),
                "image_url": image_url,
                "summary_input_type": summary_input_type,
                "source_language": language,
                "output_language": output_language,
                "translation_applied": translation_applied,
                "raw_text": text_for_summary if include_raw else None,
            }
        )

    app.logger.info(
        "request_done language=%s output_language=%s model=%s translation_model=%s items=%s article_based=%s rss_based=%s skipped_no_article=%s",
        language,
        output_language,
        model_key,
        TRANSLATION_MODEL_REF if translation_model_active else "disabled",
        len(result),
        source_type_counts.get("article", 0),
        source_type_counts.get("rss", 0),
        skipped_due_to_missing_article,
    )

    return jsonify(
        {
            "count": len(result),
            "model": model_key,
            "language": language,
            "output_language": output_language,
            "translation_model": TRANSLATION_MODEL_REF if translation_model_active else None,
            "topic": normalize_filter_value(topic),
            "country": normalize_filter_value(country).upper(),
            "region": normalize_filter_value(region),
            "available_models": list(MODEL_PATHS.keys()),
            "available_sources": NEWS_SOURCES,
            "available_languages": LANGUAGE_CONFIGS,
            "available_topics": TOPIC_CONFIGS,
            "available_regions": REGION_CONFIGS,
            "available_countries": COUNTRY_CONFIGS,
            "items": result,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=True)
