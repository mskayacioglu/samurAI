#!/usr/bin/env python3
"""Evaluate local summarization models on a labeled news dataset.

Required columns in dataset records:
- article text field (default: article)
- reference summary field (default: reference_summary)

Supported dataset formats:
- .jsonl (one JSON object per line)
- .json (list of objects, or {"items": [...]})
- .csv
- .tsv

Outputs (inside run directory):
- detailed_metrics.csv (one row per sample per model)
- model_summary.csv (aggregate mean/std per model)
- run_config.json
- report.md
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

try:
    from rouge_score import rouge_scorer
except ImportError:  # pragma: no cover
    rouge_scorer = None

try:
    import sacrebleu
except ImportError:  # pragma: no cover
    sacrebleu = None

TOKEN_RE = re.compile(r"\b[\w'-]+\b", re.UNICODE)
SENTENCE_SPLIT_RE = re.compile(r"[.!?]+")
VOWELS_RE = re.compile(r"[aeiouy]+", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate summarization models with ROUGE/BLEU plus extended metrics."
    )
    parser.add_argument("--dataset", required=True, help="Path to csv/tsv/json/jsonl dataset")
    parser.add_argument("--article-field", default="article", help="Field containing source text")
    parser.add_argument(
        "--reference-field",
        default="reference_summary",
        help="Field containing gold summary",
    )
    parser.add_argument(
        "--id-field",
        default="id",
        help="Optional record id field; row index is used when missing",
    )
    parser.add_argument(
        "--title-field",
        default="",
        help="Optional title field; if provided, title is prefixed to article",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=None,
        help="Model keys to evaluate (default: all local models)",
    )
    parser.add_argument(
        "--language",
        default="en",
        help="Language key passed to summarizer (default: en)",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=0,
        help="Optional max number of samples to evaluate (0 = all)",
    )
    parser.add_argument(
        "--allow-missing-reference",
        action="store_true",
        help="Allow rows without reference summary (ROUGE/BLEU fields remain empty)",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="Output directory (default: news_flow_web/eval_runs/run_<timestamp>)",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=10,
        help="Print progress every N samples per model",
    )
    parser.add_argument(
        "--include-summaries",
        action="store_true",
        help="Include generated summaries in detailed CSV",
    )
    return parser.parse_args()


def tokenize(text: str) -> List[str]:
    return TOKEN_RE.findall((text or "").lower())


def split_sentences(text: str) -> List[str]:
    return [s.strip() for s in SENTENCE_SPLIT_RE.split(text or "") if s.strip()]


def ngrams(tokens: Sequence[str], n: int) -> List[Tuple[str, ...]]:
    if n <= 0 or len(tokens) < n:
        return []
    return [tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


def safe_mean(values: Iterable[float]) -> Optional[float]:
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def stddev(values: Sequence[float]) -> float:
    if len(values) <= 1:
        return 0.0
    return statistics.pstdev(values)


def syllable_count(word: str) -> int:
    w = re.sub(r"[^a-z]", "", (word or "").lower())
    if not w:
        return 1
    groups = VOWELS_RE.findall(w)
    count = len(groups)
    if w.endswith("e") and count > 1:
        count -= 1
    return max(1, count)


def flesch_reading_ease(text: str) -> Optional[float]:
    tokens = tokenize(text)
    sentences = split_sentences(text)
    if not tokens or not sentences:
        return None
    total_syllables = sum(syllable_count(token) for token in tokens)
    words_per_sentence = len(tokens) / len(sentences)
    syllables_per_word = total_syllables / len(tokens)
    return 206.835 - (1.015 * words_per_sentence) - (84.6 * syllables_per_word)


def meteor_lite(reference: str, prediction: str) -> float:
    ref_tokens = tokenize(reference)
    pred_tokens = tokenize(prediction)
    if not ref_tokens or not pred_tokens:
        return 0.0

    ref_positions: Dict[str, List[int]] = defaultdict(list)
    for idx, token in enumerate(ref_tokens):
        ref_positions[token].append(idx)

    used = set()
    matched_positions: List[int] = []
    match_count = 0

    for token in pred_tokens:
        for pos in ref_positions.get(token, []):
            if pos not in used:
                used.add(pos)
                matched_positions.append(pos)
                match_count += 1
                break

    if match_count == 0:
        return 0.0

    precision = match_count / len(pred_tokens)
    recall = match_count / len(ref_tokens)
    fmean = (10 * precision * recall) / (recall + 9 * precision) if (recall + 9 * precision) else 0.0

    chunks = 1
    matched_positions.sort()
    for i in range(1, len(matched_positions)):
        if matched_positions[i] != matched_positions[i - 1] + 1:
            chunks += 1

    penalty = 0.5 * ((chunks / match_count) ** 3)
    return fmean * (1 - penalty)


def extractive_fragment_stats(source_tokens: Sequence[str], summary_tokens: Sequence[str]) -> Tuple[float, float]:
    if not source_tokens or not summary_tokens:
        return 0.0, 0.0

    src_positions: Dict[str, List[int]] = defaultdict(list)
    for j, token in enumerate(source_tokens):
        src_positions[token].append(j)

    fragments: List[int] = []
    i = 0
    while i < len(summary_tokens):
        token = summary_tokens[i]
        best_len = 0
        for j in src_positions.get(token, []):
            match_len = 0
            while (
                i + match_len < len(summary_tokens)
                and j + match_len < len(source_tokens)
                and summary_tokens[i + match_len] == source_tokens[j + match_len]
            ):
                match_len += 1
            if match_len > best_len:
                best_len = match_len

        if best_len > 0:
            fragments.append(best_len)
            i += best_len
        else:
            i += 1

    coverage = sum(fragments) / len(summary_tokens)
    density = sum(length * length for length in fragments) / len(summary_tokens)
    return coverage, density


def novelty(summary_tokens: Sequence[str], source_tokens: Sequence[str], n: int) -> float:
    summary_ngrams = ngrams(summary_tokens, n)
    source_ngrams = set(ngrams(source_tokens, n))
    if not summary_ngrams:
        return 0.0
    overlap = sum(1 for gram in summary_ngrams if gram in source_ngrams)
    return 1.0 - (overlap / len(summary_ngrams))


def repetition_ratio(tokens: Sequence[str], n: int) -> float:
    grams = ngrams(tokens, n)
    if not grams:
        return 0.0
    unique_ratio = len(set(grams)) / len(grams)
    return 1.0 - unique_ratio


def sentence_length_stats(text: str) -> Tuple[float, float]:
    sentences = split_sentences(text)
    if not sentences:
        return 0.0, 0.0
    lengths = [len(tokenize(sentence)) for sentence in sentences if sentence.strip()]
    if not lengths:
        return 0.0, 0.0
    return (sum(lengths) / len(lengths), stddev(lengths))


def ideal_sentence_length_score(avg_len: float, low: float = 8.0, high: float = 25.0) -> float:
    if avg_len <= 0:
        return 0.0
    if avg_len < low:
        return clamp01(avg_len / low)
    if avg_len > high:
        return clamp01(1.0 - ((avg_len - high) / high))
    return 1.0


def reference_metrics(reference: str, prediction: str, scorer) -> Dict[str, Optional[float]]:
    if not reference:
        return {
            "rouge1_precision": None,
            "rouge1_recall": None,
            "rouge1_fmeasure": None,
            "rouge2_precision": None,
            "rouge2_recall": None,
            "rouge2_fmeasure": None,
            "rougeL_precision": None,
            "rougeL_recall": None,
            "rougeL_fmeasure": None,
            "bleu": None,
            "meteor_lite": None,
        }

    rouge = scorer.score(reference, prediction)
    bleu = sacrebleu.sentence_bleu(prediction, [reference], smooth_method="exp").score / 100.0

    return {
        "rouge1_precision": rouge["rouge1"].precision,
        "rouge1_recall": rouge["rouge1"].recall,
        "rouge1_fmeasure": rouge["rouge1"].fmeasure,
        "rouge2_precision": rouge["rouge2"].precision,
        "rouge2_recall": rouge["rouge2"].recall,
        "rouge2_fmeasure": rouge["rouge2"].fmeasure,
        "rougeL_precision": rouge["rougeL"].precision,
        "rougeL_recall": rouge["rougeL"].recall,
        "rougeL_fmeasure": rouge["rougeL"].fmeasure,
        "bleu": bleu,
        "meteor_lite": meteor_lite(reference, prediction),
    }


def evaluate_sample(
    *,
    source_text: str,
    reference_summary: str,
    generated_summary: str,
    latency_seconds: float,
    language_key: str,
    scorer,
) -> Dict[str, Optional[float]]:
    source_tokens = tokenize(source_text)
    summary_tokens = tokenize(generated_summary)

    source_len = len(source_tokens)
    summary_len = len(summary_tokens)
    compression_ratio = (source_len / summary_len) if summary_len else 0.0

    source_vocab = set(source_tokens)
    summary_vocab = set(summary_tokens)
    source_coverage = (len(summary_vocab & source_vocab) / len(summary_vocab)) if summary_vocab else 0.0
    source_recall = (len(summary_vocab & source_vocab) / len(source_vocab)) if source_vocab else 0.0

    fragment_coverage, fragment_density = extractive_fragment_stats(source_tokens, summary_tokens)

    novelty_1gram = novelty(summary_tokens, source_tokens, 1)
    novelty_2gram = novelty(summary_tokens, source_tokens, 2)
    repetition_3gram = repetition_ratio(summary_tokens, 3)

    avg_sentence_len, sentence_len_std = sentence_length_stats(generated_summary)

    readability = None
    if language_key == "en":
        readability = flesch_reading_ease(generated_summary)

    refs = reference_metrics(reference_summary, generated_summary, scorer)

    coherence = clamp01(
        (0.50 * clamp01(1.0 - (sentence_len_std / 20.0)))
        + (0.30 * (1.0 - repetition_3gram))
        + (0.20 * ideal_sentence_length_score(avg_sentence_len))
    )

    ref_acc = safe_mean(
        [refs.get("rougeL_fmeasure"), refs.get("bleu"), refs.get("meteor_lite")]
    )
    accuracy_base = ref_acc if ref_acc is not None else source_coverage
    accuracy = clamp01((0.70 * accuracy_base) + (0.30 * source_coverage))

    readability_component = (
        clamp01((readability + 20.0) / 120.0)
        if readability is not None
        else ideal_sentence_length_score(avg_sentence_len)
    )
    clarity = clamp01((0.70 * readability_component) + (0.30 * (1.0 - repetition_3gram)))

    if refs.get("rouge1_recall") is not None:
        relevance = clamp01((0.70 * refs["rouge1_recall"]) + (0.30 * source_recall))
    else:
        relevance = clamp01(source_recall)

    factuality = clamp01((0.60 * source_coverage) + (0.40 * fragment_coverage))

    if refs.get("rouge1_recall") is not None:
        reference_len = len(tokenize(reference_summary))
        length_alignment = clamp01(1.0 - abs(summary_len - reference_len) / max(reference_len, 1))
        completeness = clamp01((0.70 * refs["rouge1_recall"]) + (0.30 * length_alignment))
    else:
        expected_min_len = max(20.0, source_len * 0.06)
        completeness = clamp01(summary_len / expected_min_len)

    latency_per_1k = latency_seconds / max(source_len / 1000.0, 1e-6)
    latency_score = 1.0 / (1.0 + latency_per_1k)
    compression_score = clamp01((compression_ratio - 2.0) / 18.0)
    efficiency = clamp01((0.60 * latency_score) + (0.40 * compression_score))

    capability_overall = safe_mean([coherence, accuracy, clarity, relevance, efficiency])

    metrics: Dict[str, Optional[float]] = {
        "source_tokens": float(source_len),
        "summary_tokens": float(summary_len),
        "compression_ratio": compression_ratio,
        "source_coverage": source_coverage,
        "source_recall": source_recall,
        "fragment_coverage": fragment_coverage,
        "fragment_density": fragment_density,
        "novelty_1gram": novelty_1gram,
        "novelty_2gram": novelty_2gram,
        "repetition_3gram": repetition_3gram,
        "avg_sentence_len": avg_sentence_len,
        "sentence_len_std": sentence_len_std,
        "flesch_reading_ease": readability,
        "latency_seconds": latency_seconds,
        "capability_coherence": coherence,
        "capability_accuracy": accuracy,
        "capability_clarity": clarity,
        "capability_relevance": relevance,
        "capability_efficiency": efficiency,
        "capability_overall": capability_overall,
        "quality_factuality": factuality,
        "quality_completeness": completeness,
    }
    metrics.update(refs)
    return metrics


def load_json_records(path: Path) -> List[dict]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        items = data.get("items")
        if isinstance(items, list):
            return [x for x in items if isinstance(x, dict)]
    raise ValueError("JSON file must be a list of objects or an object with 'items'.")


def load_jsonl_records(path: Path) -> List[dict]:
    records: List[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at line {line_no}: {exc}") from exc
            if isinstance(obj, dict):
                records.append(obj)
    return records


def load_table_records(path: Path) -> List[dict]:
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        return [dict(row) for row in reader]


def load_records(dataset_path: Path) -> List[dict]:
    suffix = dataset_path.suffix.lower()
    if suffix == ".jsonl":
        return load_jsonl_records(dataset_path)
    if suffix == ".json":
        return load_json_records(dataset_path)
    if suffix in {".csv", ".tsv"}:
        return load_table_records(dataset_path)
    raise ValueError("Unsupported dataset extension. Use .jsonl, .json, .csv or .tsv")


def normalize_row_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def prepare_samples(records: List[dict], args: argparse.Namespace) -> List[dict]:
    samples: List[dict] = []
    for idx, row in enumerate(records, start=1):
        article = normalize_row_value(row.get(args.article_field))
        reference = normalize_row_value(row.get(args.reference_field))
        sample_id = normalize_row_value(row.get(args.id_field)) or str(idx)
        title = normalize_row_value(row.get(args.title_field)) if args.title_field else ""

        if not article:
            continue
        if not reference and not args.allow_missing_reference:
            continue

        input_text = article
        if title:
            input_text = f"{title}. {article}".strip()

        samples.append(
            {
                "sample_id": sample_id,
                "title": title,
                "source_text": input_text,
                "reference_summary": reference,
            }
        )

    if args.max_samples and args.max_samples > 0:
        samples = samples[: args.max_samples]
    return samples


def write_csv(path: Path, rows: List[dict]) -> None:
    if not rows:
        return
    fieldnames: List[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def aggregate_model_metrics(rows: List[dict]) -> List[dict]:
    grouped: Dict[str, List[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["model"]].append(row)

    aggregates: List[dict] = []
    for model, model_rows in grouped.items():
        aggregate = {"model": model, "samples": len(model_rows)}

        metric_keys = [
            key
            for key in model_rows[0].keys()
            if key not in {"sample_id", "model", "language", "title", "summary"}
        ]

        for key in metric_keys:
            values = []
            for row in model_rows:
                value = row.get(key)
                if isinstance(value, (int, float)):
                    values.append(float(value))
            if values:
                aggregate[f"{key}_mean"] = sum(values) / len(values)
                aggregate[f"{key}_std"] = stddev(values)

        aggregates.append(aggregate)

    aggregates.sort(
        key=lambda x: x.get("capability_overall_mean", float("-inf")), reverse=True
    )
    return aggregates


def build_report(aggregates: List[dict]) -> str:
    if not aggregates:
        return "No results."

    lines = [
        "# Summarization Evaluation Report",
        "",
        "Bu rapor model ortalama skorlarini listeler.",
        "",
        "| Model | Capability Overall | ROUGE-L F1 | BLEU | Latency (s) | Compression |",
        "|---|---:|---:|---:|---:|---:|",
    ]

    for row in aggregates:
        lines.append(
            "| {model} | {overall:.4f} | {rougel:.4f} | {bleu:.4f} | {lat:.3f} | {comp:.2f} |".format(
                model=row["model"],
                overall=row.get("capability_overall_mean", float("nan")),
                rougel=row.get("rougeL_fmeasure_mean", float("nan")),
                bleu=row.get("bleu_mean", float("nan")),
                lat=row.get("latency_seconds_mean", float("nan")),
                comp=row.get("compression_ratio_mean", float("nan")),
            )
        )

    lines.extend(
        [
            "",
            "## Capability Proxies (0-1)",
            "",
            "- `capability_coherence`: cumle akis duzeni + dusuk tekrar + uygun cumle uzunlugu",
            "- `capability_accuracy`: referans tabanli skorlar (ROUGE-L/BLEU/METEOR-lite) + kaynak kapsama",
            "- `capability_clarity`: okunabilirlik (EN icin Flesch) + tekrar cezasi",
            "- `capability_relevance`: ROUGE-1 recall (varsa) + kaynak kelime geri cagirim",
            "- `capability_efficiency`: gecikme ve sikistirma oraninin bilesimi",
            "- `quality_factuality`: kaynakla tutarlilik (kapsama + extractive fragment)",
            "- `quality_completeness`: referans geri cagirim + uzunluk uyumu",
            "",
            "Not: Bu capability skorlar dogrudan benchmark degil, insan-merkezli kriterlere yaklasik proxy degerlerdir.",
        ]
    )

    return "\n".join(lines)


def ensure_dependencies() -> None:
    missing = []
    if rouge_scorer is None:
        missing.append("rouge-score")
    if sacrebleu is None:
        missing.append("sacrebleu")

    if missing:
        pkg_list = ", ".join(missing)
        raise SystemExit(
            f"Missing required package(s): {pkg_list}. Install with: pip install {pkg_list}"
        )


def load_summarization_runtime():
    try:
        from app import LANGUAGE_CONFIGS, MODEL_PATHS, summarize_text
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Cannot import summarization runtime from app.py. "
            f"Missing module: {exc.name}. Install project dependencies first."
        ) from exc

    return LANGUAGE_CONFIGS, MODEL_PATHS, summarize_text


def main() -> int:
    args = parse_args()

    ensure_dependencies()

    language_configs, model_paths, summarize_fn = load_summarization_runtime()

    selected_models = args.models if args.models else sorted(model_paths.keys())

    if args.language not in language_configs:
        print(
            f"[WARN] Unknown language key '{args.language}'. Continuing with provided key.",
            file=sys.stderr,
        )

    invalid_models = [m for m in selected_models if m not in model_paths]
    if invalid_models:
        raise SystemExit(
            f"Unknown model keys: {invalid_models}. Available: {sorted(model_paths.keys())}"
        )

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        raise SystemExit(f"Dataset not found: {dataset_path}")

    records = load_records(dataset_path)
    samples = prepare_samples(records, args)
    if not samples:
        raise SystemExit("No valid samples found. Check field names and dataset contents.")

    if args.output_dir:
        run_dir = Path(args.output_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = Path(__file__).resolve().parent / "eval_runs" / f"run_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    scorer = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True)

    detailed_rows: List[dict] = []
    for model in selected_models:
        print(f"[INFO] Evaluating model={model} on {len(samples)} samples")
        for idx, sample in enumerate(samples, start=1):
            start_t = time.perf_counter()
            generated = summarize_fn(sample["source_text"], model, args.language)
            latency = time.perf_counter() - start_t

            metrics = evaluate_sample(
                source_text=sample["source_text"],
                reference_summary=sample["reference_summary"],
                generated_summary=generated,
                latency_seconds=latency,
                language_key=args.language,
                scorer=scorer,
            )

            row = {
                "sample_id": sample["sample_id"],
                "model": model,
                "language": args.language,
                "title": sample["title"],
                "source_chars": len(sample["source_text"]),
                "reference_chars": len(sample["reference_summary"]),
                "summary_chars": len(generated),
            }
            row.update(metrics)
            if args.include_summaries:
                row["summary"] = generated
            detailed_rows.append(row)

            if args.progress_every > 0 and idx % args.progress_every == 0:
                print(f"[INFO] model={model} progress={idx}/{len(samples)}")

    aggregates = aggregate_model_metrics(detailed_rows)

    write_csv(run_dir / "detailed_metrics.csv", detailed_rows)
    write_csv(run_dir / "model_summary.csv", aggregates)

    config = {
        "dataset": str(dataset_path.resolve()),
        "article_field": args.article_field,
        "reference_field": args.reference_field,
        "id_field": args.id_field,
        "title_field": args.title_field,
        "models": selected_models,
        "language": args.language,
        "sample_count": len(samples),
        "generated_at": datetime.now().isoformat(),
    }
    (run_dir / "run_config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report_text = build_report(aggregates)
    (run_dir / "report.md").write_text(report_text, encoding="utf-8")

    print(f"[INFO] Evaluation completed. Outputs: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
