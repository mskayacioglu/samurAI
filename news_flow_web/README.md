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
- Varsayılan dil `en` olarak gelir; `LANGUAGE_KEY` ile değiştirilebilir.
- Her dil için birden fazla doğrudan yayıncı RSS kaynağı tanımlıdır (Google News bağımlılığı yok).
- Akış her haberde kaynak URL'sine gider, mümkünse tam haber metnini çeker ve bunun üzerinden özet üretir.

## API

`GET /api/news`

Sorgu parametreleri:
- `language`: `en`, `tr`, `fr`, `de`, `es`, `it`, `ru`, `ar`, `hi`, `zh`, `ja`, `ko`, `nl`, `ro`, `vi`
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
curl "http://localhost:8000/api/news?language=tr&sources=google_news_tr&model=mbart50_xlsum&limit=3"
```
