# samurAI

samurAI is a multilingual news summarization system that collects current articles from RSS sources, extracts full article text when possible, summarizes the content with local transformer models, and serves the results through a Flask web interface and JSON API.

The project combines a user-facing news feed with an offline ingestion pipeline, local SQLite storage, multiple summarization models, optional translation, and evaluation artifacts for comparing model behavior across languages.

## What It Does

- Collects news from curated RSS sources across multiple languages, topics, countries, and regions.
- Extracts article bodies from source pages with a fallback to RSS-provided text.
- Generates summaries using local BART, mBART, and mT5-based models.
- Stores articles, summaries, ingest runs, and model outputs in SQLite.
- Serves a filterable web feed with language, topic, region, country, source, model, keyword, image, and translation controls.
- Runs background ingestion on a scheduler instead of summarizing on every API request.
- Includes XL-Sum based evaluation notebooks, reports, metrics, and visualizations for model comparison.

## Project Structure

```text
.
|-- app/
|   |-- app.py                         # Flask application entry point
|   |-- routes.py                      # HTTP route registration
|   |-- container.py                   # Service wiring
|   |-- core_modules/                  # Catalog, RSS, extraction, summarization, translation helpers
|   |-- controllers/                   # Request handlers
|   |-- services/                      # Ingestion, feed, storage, article, model services
|   |-- static/                        # Frontend styles
|   |-- templates/                     # Web UI
|   |-- requirements.txt               # Application dependencies
|   `-- news_data.db                   # Local SQLite database
|-- data/                              # Local datasets: XL-Sum, CNN/DailyMail, Reuters
|-- models/                            # Local model directories and training notebooks
|-- evaluation/                        # Evaluation notebooks, reports, metrics, and visualizations
|-- run_server.sh                      # Convenience launcher for the Flask app
`-- tail_logs.sh                       # Convenience log follower
```

## Quick Start

Create the application environment:

```bash
cd /Users/mskayacioglu/Desktop/inf494_projet/app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the server from the project root:

```bash
cd /Users/mskayacioglu/Desktop/inf494_projet
./run_server.sh
```

Or run it directly from `app/`:

```bash
cd /Users/mskayacioglu/Desktop/inf494_projet/app
source .venv/bin/activate
INGEST_ENABLED=1 INGEST_INTERVAL_SECONDS=900 python app.py
```

Open the application at:

```text
http://localhost:8000
```

## Runtime Architecture

samurAI uses a background ingest workflow rather than generating summaries during every feed request.

```text
RSS sources
  -> article extraction
  -> text cleaning
  -> local summarization models
  -> SQLite upsert
  -> Flask API
  -> web feed
```

On startup, the application builds a service graph through `AppContainer`, registers Flask routes, initializes the SQLite database, and starts the ingest scheduler when `INGEST_ENABLED=1`.

By default:

- The first ingest run starts when the app starts.
- Later ingest runs repeat according to `INGEST_INTERVAL_SECONDS`.
- Items are distributed fairly across languages.
- Entries within each language are processed round-robin by source.
- The API reads prepared summaries from the database instead of summarizing live.

## Configuration

Important environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `PORT` | `8000` | Flask server port |
| `FLASK_DEBUG` | `0` | Enables Flask debug mode when truthy |
| `MODEL_KEY` | `mbart50_xlsum` | Default model shown in the UI |
| `LANGUAGE_KEY` | `en` | Default UI/API source language |
| `NEWS_DB_PATH` | `app/news_data.db` | SQLite database path |
| `INGEST_ENABLED` | unset | Starts the background scheduler when set to `1` |
| `INGEST_RUN_ON_START` | `1` | Runs ingestion immediately on startup |
| `INGEST_INTERVAL_SECONDS` | `900` | Delay between scheduled ingest runs |
| `INGEST_LANGUAGES` | all supported languages | Comma-separated language keys |
| `INGEST_MODEL_KEYS` | `mbart50_xlsum,mbart-xlsum-2,mt5-xlsum` | Models precomputed by ingestion |
| `INGEST_LIMIT_PER_SOURCE` | `50` | Maximum saved items per source per run |
| `INGEST_FETCH_LIMIT_PER_SOURCE` | `50` | RSS candidates fetched per source |
| `INGEST_MAX_ITEMS_PER_RUN` | `200` | Global item budget for one run |
| `INGEST_TOPIC` | empty | Optional topic filter |
| `INGEST_COUNTRY` | empty | Optional country filter |
| `INGEST_REGION` | empty | Optional region filter |
| `INGEST_SOURCES` | empty | Optional comma-separated source keys |
| `INGEST_FROM_DATE` | empty | Optional lower date bound, ISO format |
| `INGEST_UNTIL_DATE` | empty | Optional upper date bound, ISO format |
| `TRANSLATION_MODEL_REF` | empty | Optional translation model reference |

Example limited ingest run:

```bash
cd /Users/mskayacioglu/Desktop/inf494_projet/app
source .venv/bin/activate
INGEST_ENABLED=1 \
INGEST_LANGUAGES=en,tr,fr \
INGEST_MODEL_KEYS=mbart50_xlsum,mt5-xlsum \
INGEST_MAX_ITEMS_PER_RUN=60 \
python app.py
```

## Supported Languages

The application catalog supports the following language keys:

```text
en, tr, fr, de, es, it, ru, ar, hi, zh, ja, ko, nl, ro, vi
```

English can use both English-only and multilingual models. Non-English feeds are restricted to multilingual summarization models.

## Supported Models

Configured model keys:

- `bart_large_cnn`
- `bart_base_cnn`
- `bart_reuters`
- `mbart50_xlsum`
- `mbart-xlsum-2`
- `mt5-xlsum`

The multilingual default ingest set is:

```text
mbart50_xlsum, mbart-xlsum-2, mt5-xlsum
```

Model directories are expected under `models/`. The app uses local files rather than remote model downloads during normal runtime.

## Web Interface

The Flask UI at `/` provides:

- Language selection
- Topic, region, country, and source filters
- Per-source article limit
- Model selection
- Optional single-keyword search
- Optional output-language translation
- Image visibility toggle
- One-, two-, and three-column feed layouts
- Light/dark theme toggle

Each card displays the source, timestamp, image when available, generated summary, and a link to the original article.

## API

### `GET /api/news`

Returns stored summaries from SQLite.

Common query parameters:

| Parameter | Description |
| --- | --- |
| `language` | Source language key |
| `output_language` | Output language key; defaults to `language` |
| `model` | Summary model key |
| `limit` | Per-source result limit, clamped between 1 and 15 |
| `sources` | Comma-separated source keys |
| `topic` | Topic filter |
| `country` | Country filter |
| `region` | Region filter |
| `keyword_enabled` | Set to `true` to enable keyword filtering |
| `keyword` | Single-word keyword |
| `include_raw` | Set to `true` to include article text |

Example:

```bash
curl "http://localhost:8000/api/news?language=en&model=mbart50_xlsum&topic=world&limit=2"
```

### `GET /api/ingest/status`

Returns scheduler state and the latest ingest run summary.

```bash
curl "http://localhost:8000/api/ingest/status"
```

### `POST /api/ingest/run`

Queues an immediate ingest run when the scheduler is enabled.

```bash
curl -X POST "http://localhost:8000/api/ingest/run"
```

## Data and Evaluation

The repository includes local datasets and evaluation outputs used to compare summarization models.

Datasets:

- `data/xlsum/`: multilingual XL-Sum splits
- `data/cnn_dailymail/`: CNN/DailyMail parquet splits
- `data/reuters/`: Reuters-21578 data

Evaluation assets:

- `evaluation/pipelines/xlsum_model_evaluation_pipeline_full.ipynb`
- `evaluation/pipelines/xlsum_model_evaluation_pipeline200.ipynb`
- `evaluation/pipelines/xlsum_dataset_analysis_pipeline.ipynb`
- `evaluation/xlsum_eval_full/`
- `evaluation/xlsum_eval_200/`
- `evaluation/eval_visualizations/`
- `evaluation/eval_report/`

The evaluation workflow measures classical summarization metrics and project-specific capability proxies:

- ROUGE-1, ROUGE-2, ROUGE-L
- BLEU
- METEOR-lite
- Compression ratio
- Latency
- Source coverage and source recall
- Fragment coverage and fragment density
- Novel n-gram and repetition behavior
- Coherence, accuracy, clarity, relevance, efficiency
- Overall capability
- Factuality and completeness proxies

The metric definitions are documented in `evaluation/metrics.txt`.

## Notes

- RSS feeds usually expose only recent items, so historical coverage is limited by each provider.
- If article extraction fails, the system falls back to text available in the RSS entry.
- If a source RSS URL fails, the catalog logic can use Google News site-scoped RSS fallbacks.
- Database and ingest audit logs are written to `app/logs/db_operations.log`.
- Generated summaries are tied to the selected model key; switching models changes which precomputed summaries the feed reads.
