# samurAI

samurAI is a multilingual news summarization system. It collects recent articles from RSS feeds, extracts article text when possible, generates local transformer summaries, stores results in SQLite, and serves them through a Flask web interface and JSON API.

This GitHub repository contains the application code, evaluation notebooks, model-training notebooks, and project utilities. Large runtime artifacts such as datasets, model checkpoints, Hugging Face caches, SQLite databases, logs, and generated evaluation outputs are intentionally not tracked in Git.

## Features

- RSS-based news collection across 15 languages.
- Article text extraction with RSS text fallback.
- Local summarization with BART, mBART, and mT5-style sequence-to-sequence models.
- Background ingestion scheduler that precomputes summaries.
- SQLite storage for articles, summaries, model outputs, and ingest runs.
- Flask web UI with filters for language, source, topic, country, region, model, keyword, layout, images, and translation.
- JSON API for stored news summaries and ingest status.
- Evaluation notebooks for XL-Sum-based model and dataset analysis.

## Repository Layout

```text
.
|-- app/
|   |-- app.py                         # Flask app factory and server entry point
|   |-- routes.py                      # Route registration
|   |-- container.py                   # Service wiring
|   |-- core_modules/                  # RSS, catalog, extraction, summarization, translation helpers
|   |-- controllers/                   # Request handlers
|   |-- services/                      # Ingestion, feed, storage, article, model services
|   |-- static/                        # CSS
|   |-- templates/                     # Web UI
|   |-- requirements.txt               # Python dependencies
|   `-- validate_source_pool.py        # RSS source validation helper
|-- evaluation/
|   |-- metrics.txt                    # Metric definitions
|   |-- build_visualization_appendix.py
|   |-- generate_eval_visualizations.py
|   `-- pipelines/                     # Evaluation and dataset-analysis notebooks
|-- models/
|   `-- pipelines/                     # Model preparation/training notebooks
|-- run_server.sh                      # Convenience launcher
`-- tail_logs.sh                       # Convenience log follower
```

## Not Included In Git

The following are excluded because they are large, generated, machine-local, or redistributable only under their own licenses:

- `models/bart_base-cnn/`
- `models/bart_base-reuters/`
- `models/bart_large-cnn/`
- `models/mbart-large-50-many-to-many-mmt/`
- `models/mbart-xlsum-2/`
- `models/mbart50-xlsum/`
- `models/mt5-xlsum/`
- `data/`
- `app/.hf_cache/`
- `app/news_data.db`
- `app/logs/`
- `evaluation/xlsum_eval_200/`
- `evaluation/xlsum_eval_full/`
- `evaluation/eval_visualizations/`
- `evaluation/xlsum_dataset_analysis/`
- LaTeX/PDF/build/cache outputs

To run the full system, place the required local model directories under `models/` using the exact names above. Datasets should be downloaded or prepared separately under `data/` when running the notebooks.

## Quick Start

Clone the repository and create the app environment:

```bash
git clone https://github.com/mskayacioglu/samurAI.git
cd samurAI/app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Return to the project root and run the server:

```bash
cd ..
./run_server.sh
```

The application listens on:

```text
http://localhost:8000
```

Direct run from `app/`:

```bash
cd app
source .venv/bin/activate
INGEST_ENABLED=1 INGEST_INTERVAL_SECONDS=900 python app.py
```

## Model Setup

Runtime summarization uses local model files only:

```text
models/bart_large-cnn/
models/bart_base-cnn/
models/bart_base-reuters/bart-reuters-best/
models/mbart50-xlsum/
models/mbart-xlsum-2/
models/mt5-xlsum/
```

The default model key is:

```text
mbart50_xlsum
```

Configured model keys:

- `bart_large_cnn`
- `bart_base_cnn`
- `bart_reuters`
- `mbart50_xlsum`
- `mbart-xlsum-2`
- `mt5-xlsum`

Non-English feeds should use multilingual models:

```text
mbart50_xlsum, mbart-xlsum-2, mt5-xlsum
```

Optional translation uses:

```text
models/mbart-large-50-many-to-many-mmt/
```

or an explicit `TRANSLATION_MODEL_REF`.

## Runtime Configuration

Important environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `PORT` | `8000` | Flask server port |
| `FLASK_DEBUG` | `0` | Enables Flask debug mode when truthy |
| `MODEL_KEY` | `mbart50_xlsum` | Default UI/API model |
| `LANGUAGE_KEY` | `en` | Default source language |
| `NEWS_DB_PATH` | `app/news_data.db` | SQLite database path |
| `INGEST_ENABLED` | unset | Starts the scheduler when set to `1` |
| `INGEST_RUN_ON_START` | `1` | Runs ingestion immediately on startup |
| `INGEST_INTERVAL_SECONDS` | `900` | Delay between ingest runs |
| `INGEST_LANGUAGES` | all supported | Comma-separated language keys |
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
| `TRANSLATION_MODEL_REF` | local mBART-50 path if present | Optional translation model reference |

Example limited ingest run:

```bash
cd app
source .venv/bin/activate
INGEST_ENABLED=1 \
INGEST_LANGUAGES=en,tr,fr \
INGEST_MODEL_KEYS=mbart50_xlsum,mt5-xlsum \
INGEST_MAX_ITEMS_PER_RUN=60 \
python app.py
```

## Supported Languages

```text
en, tr, fr, de, es, it, ru, ar, hi, zh, ja, ko, nl, ro, vi
```

English can use English-only and multilingual models. Other languages are restricted to multilingual summarization models.

## API

### `GET /api/news`

Returns summaries stored in SQLite.

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

## Evaluation

The repository keeps notebooks and scripts for reproducing the evaluation workflow:

- `evaluation/pipelines/xlsum_dataset_analysis_pipeline.ipynb`
- `evaluation/pipelines/xlsum_model_evaluation_pipeline200.ipynb`
- `evaluation/pipelines/xlsum_model_evaluation_pipeline_full.ipynb`
- `evaluation/generate_eval_visualizations.py`
- `evaluation/build_visualization_appendix.py`
- `evaluation/metrics.txt`

Generated reports, full prediction files, figures, spreadsheets, and LaTeX build outputs are not committed. Recreate them locally after preparing the required datasets and model directories.

The evaluation workflow covers:

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

## Notes

- RSS feeds usually expose only recent items, so historical coverage depends on each provider.
- If article extraction fails, the system falls back to text available in the RSS entry.
- If a source RSS URL fails, catalog logic can use Google News site-scoped RSS fallbacks.
- The SQLite database and audit logs are generated locally.
- Generated summaries are tied to the selected model key; switching models changes which precomputed summaries the feed reads.
