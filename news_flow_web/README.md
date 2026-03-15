# News Summary Flow

Bu uygulama, belirlediğiniz RSS haber kaynaklarından güncel haber başlık/açıklamalarını çeker, yerel özetleme modelinizle özetler ve kaynak linkleriyle bir akış ekranında gösterir.

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

Varsayılan model `bart_large_cnn` olarak gelir. Farklı modeli varsayılan yapmak için:

```bash
MODEL_KEY=bart_reuters python app.py
```

Desteklenen model anahtarları:
- `bart_large_cnn`
- `bart_base_cnn`
- `bart_reuters`

## API

`GET /api/news`

Sorgu parametreleri:
- `source`: `bbc_world`, `guardian_world`, `aljazeera_all` veya boş (hepsi)
- `model`: model anahtarı
- `limit`: kaynak başına haber adedi (1-15)
- `include_raw`: `true|false`

Örnek:

```bash
curl "http://localhost:8000/api/news?source=bbc_world&model=bart_large_cnn&limit=3"
```
