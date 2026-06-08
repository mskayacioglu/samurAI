"""News catalog, locale, topic, and source configuration."""

from .runtime import *

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
    """Return a lowercase underscore key derived from display text."""
    raw = unescape(str(text or "")).replace("\xa0", " ")
    value = re.sub(r"\s+", " ", raw).strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def google_news_locale(language_key: str, country_key: str):
    """Return Google News locale parameters for a language and country."""
    hint = GOOGLE_NEWS_LOCALE_HINTS.get(language_key)
    if hint:
        return hint["hl"], hint["gl"], hint["ceid"]
    country = (country_key or "US").upper()
    return "en-US", country, f"{country}:en"


def topic_query_term(topic_key: str, language_key: str) -> str:
    """Return the localized query term for a topic key."""
    lang_terms = TOPIC_QUERY_TERMS.get(language_key, TOPIC_QUERY_TERMS.get("en", {}))
    return lang_terms.get(topic_key, topic_key)


def build_google_news_rss_url(query: str, language_key: str, country_key: str) -> str:
    """Build a Google News RSS search URL for a query and locale."""
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
    """Build optional Google News topic sources from language seed domains."""
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
    """Build optional Google News topic sources from per-language overrides."""
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
    """Build curated topic-specific source aliases from base source pools."""

    def norm(value: str) -> str:
        """Normalize source metadata text for matching."""
        return re.sub(r"\s+", " ", str(value or "")).strip()

    def infer_candidate_topic(source: dict) -> str:
        """Infer a topic key for a source candidate."""
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
        """Score how closely a source topic matches a target topic."""
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
    """Load source keys that failed the latest dynamic quality report."""
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
    """Infer a source topic from explicit config or source metadata."""
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
    """Infer the country key for a source configuration."""
    explicit = re.sub(r"\s+", " ", str(source_cfg.get("country", "") or "")).strip().upper()
    if explicit in COUNTRY_CONFIGS:
        return explicit
    if source_key in SOURCE_COUNTRY_HINTS:
        return SOURCE_COUNTRY_HINTS[source_key]
    return LANGUAGE_DEFAULT_COUNTRY.get(language_key, "US")


def infer_region(country_key: str, source_cfg: dict) -> str:
    """Infer the region key for a source from country and config."""
    explicit = re.sub(r"\s+", " ", str(source_cfg.get("region", "") or "")).strip().lower()
    if explicit in REGION_CONFIGS:
        return explicit
    return COUNTRY_CONFIGS.get(country_key, {}).get("region", "global")


def source_site_key(source_cfg: dict) -> str:
    """Return a normalized domain key used to deduplicate sources."""
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
    """Merge, filter, deduplicate, and enrich all configured sources."""
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

__all__ = [name for name in globals() if not name.startswith("__")]
