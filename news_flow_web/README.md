# News Summary Flow

Bu uygulama, belirlediğiniz RSS haber kaynaklarından güncel haberleri çeker, mümkünse kaynak linkindeki tam haber metnini indirir, yerel özetleme modelinizle özetler ve kaynak linkleriyle bir akış ekranında gösterir. Kaynak sayfadan metin çıkarılamazsa RSS açıklamasına geri düşer.

## Kurulum

```bash
cd /Users/mskayacioglu/Desktop/inf494_projet/news_flow_web
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Çalıştırma

```bash
python app.py
```

Ardından tarayıcıdan:

`http://localhost:8000`

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

Not:
- İngilizce dışı dillerde API, otomatik olarak `mbart50_xlsum` modelini kullanır.
- Çeviri katmanı opsiyoneldir. `TRANSLATION_MODEL_REF` set edilirse başlık/özet hedef dile çevrilebilir.
- Varsayılan dil `en` olarak gelir; `LANGUAGE_KEY` ile değiştirilebilir.
- Her dil için popüler kaynak havuzu + kategori bazlı ek kaynaklar otomatik üretilir.
- Kategori seti: `general`, `world`, `politics`, `business`, `technology`, `science`, `health`, `sports`, `entertainment`, `culture`.
- Bir kaynakta doğrudan RSS başarısız olursa sistem otomatik Google News site-scope RSS fallback uygular; böylece seçeneklerdeki kaynakların RSS erişimi korunur.
- Varsayılan olarak kalite kapısı açıktır (`ENABLE_SOURCE_QUALITY_GATE=1`): düşük kalite verdiği bilinen kaynaklar seçeneklerde gizlenir.
- Dinamik kalite kapısı opsiyoneldir (`ENABLE_DYNAMIC_QUALITY_GATE=1`): en son `source_validation_reports/*.json` raporundaki başarısız kaynaklar da otomatik gizlenir.
- Google News topic-source üretimi varsayılan kapalıdır (`ENABLE_GOOGLE_TOPIC_SOURCES=0`), istenirse açılabilir.
- Akış her haberde kaynak URL'sine gider, mümkünse tam haber metnini çeker ve bunun üzerinden özet üretir.
- Özetleme girdisinde model sadece haber gövdesini alır (başlık modele verilmez); başlık arayüzde ayrı gösterilir.
- `SOURCE_OVERSAMPLE_FACTOR` (varsayılan `4`) ile kaynak başına daha fazla aday link çekilip, çekilemeyen haberler yerine yeni adaylar denenir.
- API yanıtındaki her haber için `image_url` alanı da döner (önce RSS medya alanları, yoksa haber sayfası `og:image`/`twitter:image`).

## Model Değerlendirme (ROUGE/BLEU + Extended)

Haber özetleme modellerini karşılaştırmak için `evaluate_models.py` script'i eklendi.

### Desteklenen veri formatı

- `jsonl`, `json`, `csv`, `tsv`
- Zorunlu alanlar:
  - `article` (kaynak metin)
  - `reference_summary` (insan referans özeti)
- Opsiyonel alanlar:
  - `id`
  - `title`

Örnek veri:

`news_flow_web/examples/eval_dataset.sample.jsonl`

### Çalıştırma örneği

```bash
cd /Users/mskayacioglu/Desktop/inf494_projet/news_flow_web
./run_evaluation.sh \
  --dataset examples/eval_dataset.sample.jsonl \
  --article-field article \
  --reference-field reference_summary \
  --title-field title \
  --models bart_large_cnn bart_base_cnn bart_reuters mbart50_xlsum \
  --language en \
  --include-summaries
```

`run_evaluation.sh` script'i otomatik olarak:
- `.venv` yoksa oluşturur
- `requirements.txt` bağımlılıklarını kurar
- `evaluate_models.py` script'ini çalıştırır

### Üretilen çıktılar

Script varsayılan olarak `news_flow_web/eval_runs/run_<timestamp>/` altında üretir:

- `detailed_metrics.csv`: örnek-bazlı skorlar
- `model_summary.csv`: model ortalama/std skorlar
- `report.md`: hızlı karşılaştırma tablosu
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
  - `capability_coherence`
  - `capability_accuracy`
  - `capability_clarity`
  - `capability_relevance`
  - `capability_efficiency`
  - `capability_overall`
- Ek kalite proxy skorları (0-1):
  - `quality_factuality`
  - `quality_completeness`

## API

`GET /api/news`

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
cd /Users/mskayacioglu/Desktop/inf494_projet/news_flow_web
python validate_source_pool.py --language __all__ --sample-links 2 --workers 8
```

Örnek daraltılmış koşu:

```bash
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
