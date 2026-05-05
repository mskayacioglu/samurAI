# News Summary Flow

Bu uygulama, belirlediğiniz RSS haber kaynaklarından güncel haberleri çeker, mümkünse kaynak linkindeki tam haber metnini indirir, yerel özetleme modelinizle özetler ve kaynak linkleriyle bir akış ekranında gösterir. Kaynak sayfadan metin çıkarılamazsa RSS açıklamasına geri düşer.

## Kurulum

```bash
cd /Users/mskayacioglu/Desktop/inf494_projet/app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd /Users/mskayacioglu/Desktop/inf494_projet/evaluation
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Çalıştırma

```bash
cd /Users/mskayacioglu/Desktop/inf494_projet/app
source .venv/bin/activate
INGEST_ENABLED=1 INGEST_INTERVAL_SECONDS=900 python app.py
```

Ardından tarayıcıdan:

`http://localhost:8000`


## Sürekli Çalışan Mimari (Scheduler + DB)

Uygulama artık haberleri `GET /api/news` çağrısı sırasında canlı çekmek yerine, arka planda sürekli çalışan ingest job'u ile düzenli aralıklarla toplar ve veritabanına yazar.

Akış:
- Scheduler (`INGEST_INTERVAL_SECONDS`)
- RSS toplama + makale gövdesi çıkarımı
- Özet üretimi
- SQLite veritabanına upsert (`app/news_data.db`)
- API'nin DB'den okuması

Varsayılan davranış:
- Uygulama açılışında ilk ingest otomatik koşar (`INGEST_RUN_ON_START=1`)
- Sonrasında belirlenen aralıkta ingest tekrar eder
- Varsayılan olarak tüm diller ve tüm kaynaklar ingest edilir
- Varsayılan model seti: `mbart50_xlsum,mbart-xlsum-2,mt5-xlsum`
- `GET /api/news` sadece DB'deki hazır özetleri döner; API çağrısında tekrar özetleme yapmaz
- Her turda dil başına adil kota uygulanır (fair-share), tek dilin tüm limiti tüketmesi engellenir
- Dil içinde kaynaklar round-robin işlenir, tek kaynağın diğerlerini baskılaması engellenir
- Tur `INGEST_MAX_ITEMS_PER_RUN` limitine ulaştıysa scheduler beklemeden yeni tura geçer

Önemli environment değişkenleri:
- `INGEST_ENABLED=1`
- `INGEST_RUN_ON_START=1`
- `INGEST_INTERVAL_SECONDS=900`
- `INGEST_LANGUAGES` (boş bırakılırsa tüm diller)
- `INGEST_MODEL_KEYS=mbart50_xlsum,mbart-xlsum-2,mt5-xlsum`
- `INGEST_LIMIT_PER_SOURCE=50`
- `INGEST_FETCH_LIMIT_PER_SOURCE=50` (source başına RSS'den çekilecek aday sayısı)
- `INGEST_MAX_ITEMS_PER_RUN=200`
- `INGEST_FROM_DATE=2026-03-01T00:00:00Z` (opsiyonel alt tarih sınırı)
- `INGEST_UNTIL_DATE=2026-03-29T23:59:59Z` (opsiyonel üst tarih sınırı)
- `INGEST_TOPIC`, `INGEST_COUNTRY`, `INGEST_REGION`, `INGEST_SOURCES` (opsiyonel filtreler)
- `NEWS_DB_PATH=/absolute/path/news_data.db` (opsiyonel, verilmezse `app/news_data.db`)

Not:
- RSS kaynakları çoğunlukla son N haberi verir; bu nedenle "belirli tarihe kadar tüm geçmiş" kapsamı kaynağın sağladığı feed geçmişiyle sınırlıdır.
- DB yazım denetim logu: `app/logs/db_operations.log` (insert/update ingest run kayıtları).

## Model Seçimi

Varsayılan model `mbart50_xlsum` olarak gelir. Farklı modeli varsayılan yapmak için:

```bash
MODEL_KEY=bart_reuters python app.py
```

Desteklenen model anahtarları:
- `bart_large_cnn`
- `bart_base_cnn`
- `bart_reuters`
- `mbart50_xlsum` (15 dil için çok dilli özetleme modeli)
- `mbart-xlsum-2` (15 dil için çok dilli özetleme modeli)
- `mt5-xlsum` (15 dil için çok dilli özetleme modeli)

Not:
- İngilizce dışı dillerde API, sadece çok dilli modelleri (`mbart50_xlsum`, `mbart-xlsum-2`, `mt5-xlsum`) kabul eder; geçersiz seçimde `mbart50_xlsum` kullanılır.
- Çeviri katmanı opsiyoneldir. `TRANSLATION_MODEL_REF` set edilirse başlık/özet hedef dile çevrilebilir.
- Varsayılan dil `en` olarak gelir; `LANGUAGE_KEY` ile değiştirilebilir.
- Her dil için popüler kaynak havuzu + kategori bazlı ek kaynaklar otomatik üretilir.
- Kategori seti: `general`, `world`, `politics`, `business`, `technology`, `science`, `health`, `sports`, `entertainment`, `culture`.
- Bir kaynakta doğrudan RSS başarısız olursa sistem otomatik Google News site-scope RSS fallback uygular; böylece seçeneklerdeki kaynakların RSS erişimi korunur.
- Varsayılan olarak kalite kapısı açıktır (`ENABLE_SOURCE_QUALITY_GATE=1`): düşük kalite verdiği bilinen kaynaklar seçeneklerde gizlenir.
- Dinamik kalite kapısı opsiyoneldir (`ENABLE_DYNAMIC_QUALITY_GATE=1`): en son `source_validation_reports/*.json` raporundaki başarısız kaynaklar da otomatik gizlenir.
- Varsayılan olarak kategori başına ek havuz genişletme aktiftir (`ENABLE_CURATED_TOPIC_SOURCES=1`): her dilin her kategorisine popüler RSS kaynaklarından ek girişler üretilir.
- Kategori başına üretilecek ek kaynak adedi `CATEGORY_SOURCES_PER_TOPIC` ile ayarlanır (varsayılan `3`).
- Google News topic-source üretimi varsayılan kapalıdır (`ENABLE_GOOGLE_TOPIC_SOURCES=0`), istenirse açılabilir.
- Akış her haberde kaynak URL'sine gider, mümkünse tam haber metnini çeker ve bunun üzerinden özet üretir.
- Özetleme girdisinde model sadece haber gövdesini alır (başlık modele verilmez); başlık arayüzde ayrı gösterilir.
- `SOURCE_OVERSAMPLE_FACTOR` (varsayılan `4`) ile kaynak başına daha fazla aday link çekilip, çekilemeyen haberler yerine yeni adaylar denenir.
- API yanıtındaki her haber için `image_url` alanı da döner (önce RSS medya alanları, yoksa haber sayfası `og:image`/`twitter:image`).

## Model Değerlendirme (XL-Sum + Section 2.4 Metrikleri + PDF)

Haber özetleme modellerini karşılaştırmak için `evaluate_models.py` script'i eklendi.

Colab/A100 üzerinde Drive'daki modellerle çalışmak için hazır notebook:

`models/pipelines/xlsum_model_evaluation_pipeline.ipynb`

Notebook varsayılan olarak:
- Google Drive'ı mount eder
- `DRIVE_PROJECT_ROOT=/content/drive/MyDrive/inf494_projet` altındaki modelleri okur
- XL-Sum `test` split'ini kullanır ve `train` split'ini engeller
- İngilizce BART modellerini sadece `en` üzerinde, çok dilli modelleri XL-Sum'da mevcut seçili dillerde ölçer
- `detailed_metrics.csv`, `model_language_summary.csv`, `model_overall_macro_summary.csv`, `skipped_models.csv`, `xlsum_evaluation_report.xlsx`, `report.md` ve grafikler üretir

Not: Projedeki 15 dil listesinde `de`, `it`, `nl`, `ro` yer alır; public `csebuetnlp/xlsum` sürümünde bu dört dil için eşleşen subset yoksa notebook bunları `language_plan` sheet'inde skipped olarak raporlar.

### Desteklenen veri formatı

- `jsonl`, `json`, `csv`, `tsv`
- Zorunlu alanlar:
  - `article` (kaynak metin)
  - `reference_summary` (insan referans özeti)
- Opsiyonel alanlar:
  - `id`
  - `title`

Örnek veri:

`evaluation/examples/eval_dataset.sample.jsonl`

### Çalıştırma örneği

```bash
cd /Users/mskayacioglu/Desktop/inf494_projet/evaluation
source .venv/bin/activate
./run_evaluation.sh \
  --dataset ./examples/eval_dataset.sample.jsonl \
  --article-field article \
  --reference-field reference_summary \
  --title-field title \
  --models bart_large_cnn bart_base_cnn bart_reuters mbart50_xlsum \
  --language en \
  --include-summaries
```

XL-Sum üzerinden doğrudan değerlendirme örneği:

```bash
cd /Users/mskayacioglu/Desktop/inf494_projet/evaluation
source .venv/bin/activate
./run_evaluation.sh \
  --use-xlsum \
  --xlsum-language auto \
  --xlsum-split test \
  --models mbart50_xlsum mbart-xlsum-2 mt5-xlsum \
  --language __all__ \
  --max-samples 100 \
  --include-summaries
```

Bu komut, projedeki 15 dil anahtarını (`en,tr,fr,de,es,it,ru,ar,hi,zh,ja,ko,nl,ro,vi`) dener; public XL-Sum'da eşleşen subset'i olmayan dilleri skipped olarak raporlar.

`run_evaluation.sh` script'i otomatik olarak:
- `.venv` yoksa oluşturur
- `requirements.txt` bağımlılıklarını kurar
- `evaluate_models.py` script'ini çalıştırır

### Üretilen çıktılar

Script varsayılan olarak `evaluation/eval_runs/run_<timestamp>/` altında üretir:

- `detailed_metrics.csv`: örnek-bazlı skorlar
- `model_summary.csv`: model ortalama/std skorlar
- `report.md`: hızlı karşılaştırma tablosu
- `report.pdf`: sunum/rapor için PDF çıktı
- `run_config.json`: koşu konfigürasyonu

### Hesaplanan metrikler

- Klasik:
  - `ROUGE-1`, `ROUGE-2`, `ROUGE-L` (precision/recall/f1)
  - `BLEU`
- Ek:
  - `METEOR-lite` (referans bazlı)
  - `compression_ratio`, `latency_seconds`
  - `source_coverage`, `source_recall`
  - `fragment_coverage`, `fragment_density` (extractiveness)
  - `novelty_1gram`, `novelty_2gram`, `repetition_3gram`
- İnsan-merkezli capability proxy skorları (0-1):
  - `capability_coherence` (Coherence)
  - `capability_accuracy` (Accuracy)
  - `capability_clarity` (Clarity)
  - `capability_relevance` (Relevance)
  - `capability_efficiency` (Efficiency)
  - `capability_overall`
- Ek kalite proxy skorları (0-1):
  - `quality_factuality`
  - `quality_completeness`

Not:
- Section 2.4'teki kriterler (coherence, accuracy, clarity, relevance, efficiency) bu projede ölçülebilir proxy metriklerle operasyonelleştirilmiştir.

## API

`GET /api/news`

Not: Bu endpoint artık sonuçları veritabanından döner. Arka plan ingest'i henüz çalışmadıysa boş liste dönebilir.

Ek endpointler:
- `GET /api/ingest/status`: scheduler durumu + son ingest run özeti
- `POST /api/ingest/run`: ingest'i hemen kuyruğa alır

Sorgu parametreleri:
- `language`: `en`, `tr`, `fr`, `de`, `es`, `it`, `ru`, `ar`, `hi`, `zh`, `ja`, `ko`, `nl`, `ro`, `vi`
- `output_language`: çıktı dili (verilmezse `language` ile aynı kabul edilir)
- `topic`: haber türü filtresi (`general`, `world`, `sports` veya `__all__`)
- `topic`: haber türü filtresi (`general`, `world`, `politics`, `business`, `technology`, `science`, `health`, `sports`, `entertainment`, `culture` veya `__all__`)
- `region`: bölge filtresi (örn. `europe`, `asia`, `oceania`, `middle_east`, `north_america`, `global` veya `__all__`)
- `country`: ülke filtresi (ISO-2 kodu, örn. `TR`, `US`, `GB` veya `__all__`)
- `sources`: virgülle ayrılmış kaynak anahtarları (ör: `bbc_world,guardian_world`)
- `source`: geriye dönük tekil kaynak parametresi (`sources` verilmezse kullanılır)
- `model`: model anahtarı
- `limit`: kaynak başına haber adedi (1-15)
- `include_raw`: `true|false`

Yanıtta her haber için `summary_input_type` alanı bulunur:
- `article`: özet, kaynak sayfadan çıkarılan metinle üretildi
- `rss`: kaynak metin çekilemedi, RSS başlık/açıklama ile üretildi

Örnek:

```bash
curl "http://localhost:8000/api/news?language=tr&output_language=en&topic=sports&region=europe&country=TR&sources=tr_ntvspor,tr_hurriyet_spor,tr_sabah_spor&model=mbart50_xlsum&limit=3"
```

## Çeviri modelini açma

Varsayılan durumda uygulama, varsa local `models/mbart-large-50-many-to-many-mmt` klasörünü otomatik çeviri modeli olarak kullanır. Elle set etmek için:

```bash
TRANSLATION_MODEL_REF=facebook/mbart-large-50-many-to-many-mmt python app.py
```

## Kaynak Havuzu Doğrulama (RSS + Body Kalite)

Kaynakların erişim ve içerik kalitesini otomatik test etmek için:

```bash
cd /Users/mskayacioglu/Desktop/inf494_projet/app
source .venv/bin/activate
python validate_source_pool.py --language __all__ --sample-links 2 --workers 8 --output-dir ../evaluation/source_validation_reports
```

Örnek daraltılmış koşu:

```bash
cd /Users/mskayacioglu/Desktop/inf494_projet/app
source .venv/bin/activate
python validate_source_pool.py --language tr --topic business --max-sources 40
```

Script çıktıları:
- `source_validation_reports/source_validation_<timestamp>.json`
- `source_validation_reports/source_validation_<timestamp>.md`

Rapor her kaynak için:
- RSS erişim başarısı ve entry sayısı
- Çekilen article body uzunluğu / kalite skoru
- Özet tohum kalitesi (`extractive_fallback` dejenere kontrolü)
- Geçti/Kaldı durumu ve nedenleri

Not:
- `--min-article-chars` eşiği varsayılan `300`'dür; `ja/ko/zh` için script otomatik olarak bu eşiğin `%70` değerini kullanır (CJK metin yoğunluğu nedeniyle).
