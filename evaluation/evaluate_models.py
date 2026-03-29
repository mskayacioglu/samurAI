#!/usr/bin/env python3
"""Evaluate local summarization models on a labeled news dataset or XL-Sum.

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
- report.pdf
"""

from __future__ import annotations

import argparse
import copy
import csv
import importlib
import json
import re
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
APP_DIR = PROJECT_ROOT / "app"

try:
    from rouge_score import rouge_scorer
except ImportError:  # pragma: no cover
    rouge_scorer = None

try:
    import sacrebleu
except ImportError:  # pragma: no cover
    sacrebleu = None

try:
    from datasets import load_dataset
except ImportError:  # pragma: no cover
    load_dataset = None

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
except ImportError:  # pragma: no cover
    A4 = None

TOKEN_RE = re.compile(r"\b[\w'-]+\b", re.UNICODE)
SENTENCE_SPLIT_RE = re.compile(r"[.!?]+")
VOWELS_RE = re.compile(r"[aeiouy]+", re.IGNORECASE)

XLSUM_BY_LANGUAGE_KEY = {
    "en": "english",
    "tr": "turkish",
    "fr": "french",
    "de": "german",
    "es": "spanish",
    "it": "italian",
    "ru": "russian",
    "ar": "arabic",
    "hi": "hindi",
    "zh": "chinese_simplified",
    "ja": "japanese",
    "ko": "korean",
    "nl": "dutch",
    "ro": "romanian",
    "vi": "vietnamese",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate summarization models with ROUGE/BLEU plus "
            "human-centered capability metrics."
        )
    )
    parser.add_argument("--dataset", default="", help="Path to csv/tsv/json/jsonl dataset")
    parser.add_argument(
        "--use-xlsum",
        action="store_true",
        help="Load dataset from Hugging Face XL-Sum instead of a local file",
    )
    parser.add_argument(
        "--xlsum-language",
        default="auto",
        help="XL-Sum language subset; use 'auto' to map from language key",
    )
    parser.add_argument(
        "--xlsum-split",
        default="test",
        help="XL-Sum split (default: test)",
    )
    parser.add_argument(
        "--xlsum-cache-dir",
        default="",
        help="Optional Hugging Face datasets cache directory",
    )
    parser.add_argument(
        "--xlsum-shuffle-seed",
        type=int,
        default=42,
        help="Shuffle seed applied before max-samples slicing (XL-Sum mode)",
    )
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
        help="Language key passed to summarizer; use __all__ for all language keys",
    )
    parser.add_argument(
        "--languages",
        nargs="+",
        default=None,
        help="Optional explicit list of language keys (overrides --language)",
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
        help="Output directory (default: evaluation/eval_runs/run_<timestamp>)",
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


def load_xlsum_records(
    *,
    language: str,
    split: str,
    cache_dir: str,
    shuffle_seed: int,
) -> List[dict]:
    if load_dataset is None:
        raise SystemExit(
            "Missing required package(s): datasets. Install with: pip install datasets"
        )

    kwargs = {"path": "csebuetnlp/xlsum", "name": language, "split": split}
    if cache_dir:
        kwargs["cache_dir"] = cache_dir

    try:
        dataset = load_dataset(**kwargs)
    except Exception as exc:
        raise SystemExit(
            f"Failed to load XL-Sum ({language}/{split}): {exc}"
        ) from exc

    if shuffle_seed is not None:
        dataset = dataset.shuffle(seed=shuffle_seed)
    return [dict(record) for record in dataset]


def resolve_selected_languages(
    language_configs: Dict[str, dict], language_arg: str, languages_arg: Optional[List[str]]
) -> List[str]:
    if languages_arg:
        selected = languages_arg
    elif language_arg == "__all__":
        selected = sorted(language_configs.keys())
    else:
        selected = [language_arg]

    invalid = [lang for lang in selected if lang not in language_configs]
    if invalid:
        raise SystemExit(
            f"Unknown language key(s): {invalid}. Available: {sorted(language_configs.keys())}"
        )
    return selected


def resolve_xlsum_subset(language_key: str, xlsum_language_arg: str) -> str:
    if xlsum_language_arg and xlsum_language_arg != "auto":
        return xlsum_language_arg
    subset = XLSUM_BY_LANGUAGE_KEY.get(language_key)
    if not subset:
        raise SystemExit(
            f"No XL-Sum subset mapping for language key '{language_key}'. "
            "Pass --xlsum-language explicitly."
        )
    return subset


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
    grouped: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
    for row in rows:
        grouped[(row["language"], row["model"])].append(row)

    aggregates: List[dict] = []
    for (language, model), model_rows in grouped.items():
        aggregate = {"language": language, "model": model, "samples": len(model_rows)}

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
        key=lambda x: (x.get("language", ""), -x.get("capability_overall_mean", float("-inf")))
    )
    return aggregates


def build_report(aggregates: List[dict]) -> str:
    if not aggregates:
        return "No results."

    lines = [
        "# XL-Sum / Summarization Evaluation Report",
        "",
        "Bu rapor model ortalama skorlarini listeler.",
        "Metrikler, arXiv:2505.08253v1 (Section 2.4) cizgisindeki 5 insan-merkezli kaliteye gore raporlanmistir.",
        "",
        "| Language | Model | Overall (2.4) | Coherence | Accuracy | Clarity | Relevance | Efficiency | ROUGE-L F1 | BLEU |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for row in aggregates:
        lines.append(
            "| {language} | {model} | {overall:.4f} | {coh:.4f} | {acc:.4f} | {cla:.4f} | {rel:.4f} | {eff:.4f} | {rougel:.4f} | {bleu:.4f} |".format(
                language=row.get("language", "-"),
                model=row["model"],
                overall=row.get("capability_overall_mean", float("nan")),
                coh=row.get("capability_coherence_mean", float("nan")),
                acc=row.get("capability_accuracy_mean", float("nan")),
                cla=row.get("capability_clarity_mean", float("nan")),
                rel=row.get("capability_relevance_mean", float("nan")),
                eff=row.get("capability_efficiency_mean", float("nan")),
                rougel=row.get("rougeL_fmeasure_mean", float("nan")),
                bleu=row.get("bleu_mean", float("nan")),
            )
        )

    lines.extend(
        [
            "",
            "## Evaluation of Metrics (Section 2.4 Alignment)",
            "",
            "- `coherence`: dogal akicilik proxysi (cumle ritmi + tekrar cezasi + cumle uzunlugu dengesi).",
            "- `accuracy`: referans dogruluk proxysi (ROUGE-L/BLEU/METEOR-lite + kaynak kapsama).",
            "- `clarity`: anlasilabilirlik proxysi (okunabilirlik/sadelik + tekrar cezasi).",
            "- `relevance`: konu kapsami proxysi (ROUGE-1 recall + source recall).",
            "- `efficiency`: pratik verim proxysi (latency + compression).",
            "- `quality_factuality`: kaynakla tutarlilik (kapsama + extractive fragment)",
            "- `quality_completeness`: referans geri cagirim + uzunluk uyumu",
            "",
            "Not: Bu skorlar dogrudan insan anotasyonu degil, 2.4 kriterlerini operasyonel hale getiren proxy degerlerdir.",
        ]
    )

    return "\n".join(lines)


def _fmt_score(value: Optional[float], digits: int = 4) -> str:
    if value is None:
        return "-"
    return f"{value:.{digits}f}"


def generate_pdf_report(path: Path, aggregates: List[dict], config: dict) -> bool:
    if A4 is None:
        return False

    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=1.6 * cm, leftMargin=1.6 * cm)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Summarization Evaluation Report (XL-Sum)", styles["Title"]))
    story.append(Spacer(1, 0.4 * cm))
    story.append(
        Paragraph(
            (
                "Metrics follow the Section 2.4 framing from arXiv:2505.08253v1 "
                "(coherence, accuracy, clarity, relevance, efficiency)."
            ),
            styles["BodyText"],
        )
    )
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(f"Generated at: {config.get('generated_at', '-')}", styles["BodyText"]))
    story.append(Paragraph(f"Dataset: {config.get('dataset', '-')}", styles["BodyText"]))
    story.append(Paragraph(f"Sample count: {config.get('sample_count', '-')}", styles["BodyText"]))
    story.append(Paragraph(f"Language key: {config.get('language', '-')}", styles["BodyText"]))
    story.append(Spacer(1, 0.5 * cm))

    table_data = [
        [
            "Lang",
            "Model",
            "Overall",
            "Coherence",
            "Accuracy",
            "Clarity",
            "Relevance",
            "Efficiency",
            "ROUGE-L",
            "BLEU",
        ]
    ]

    for row in aggregates:
        table_data.append(
            [
                row.get("language", "-"),
                row.get("model", "-"),
                _fmt_score(row.get("capability_overall_mean")),
                _fmt_score(row.get("capability_coherence_mean")),
                _fmt_score(row.get("capability_accuracy_mean")),
                _fmt_score(row.get("capability_clarity_mean")),
                _fmt_score(row.get("capability_relevance_mean")),
                _fmt_score(row.get("capability_efficiency_mean")),
                _fmt_score(row.get("rougeL_fmeasure_mean")),
                _fmt_score(row.get("bleu_mean")),
            ]
        )

    col_widths = [1.4 * cm, 2.8 * cm, 1.6 * cm, 1.7 * cm, 1.7 * cm, 1.7 * cm, 1.7 * cm, 1.7 * cm, 1.6 * cm, 1.6 * cm]
    table = Table(table_data, repeatRows=1, colWidths=col_widths)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EDF4")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9EA8B3")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ]
        )
    )
    story.append(table)

    doc.build(story)
    return True


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
    app_dir_str = str(APP_DIR)
    if app_dir_str not in sys.path:
        sys.path.insert(0, app_dir_str)

    for module_name in ["core", "app"]:
        existing_module = sys.modules.get(module_name)
        if existing_module:
            del sys.modules[module_name]

    try:
        runtime = importlib.import_module("core")
    except ModuleNotFoundError as exc:
        try:
            runtime = importlib.import_module("app")
        except ModuleNotFoundError:
            raise SystemExit(
                "Cannot import summarization runtime from app/core.py or app/app.py. "
                f"Missing module: {exc.name}. Install project dependencies first."
            ) from exc

    required = ["LANGUAGE_CONFIGS", "MODEL_PATHS", "summarize_text"]
    missing = [name for name in required if not hasattr(runtime, name)]
    if missing:
        raise SystemExit(
            f"Runtime module loaded from {app_module_path} but missing members: {', '.join(missing)}"
        )

    return runtime.LANGUAGE_CONFIGS, runtime.MODEL_PATHS, runtime.summarize_text


def main() -> int:
    args = parse_args()

    ensure_dependencies()

    language_configs, model_paths, summarize_fn = load_summarization_runtime()

    selected_models = args.models if args.models else sorted(model_paths.keys())

    selected_languages = resolve_selected_languages(
        language_configs=language_configs,
        language_arg=args.language,
        languages_arg=args.languages,
    )

    invalid_models = [m for m in selected_models if m not in model_paths]
    if invalid_models:
        raise SystemExit(
            f"Unknown model keys: {invalid_models}. Available: {sorted(model_paths.keys())}"
        )

    shared_records: Optional[List[dict]] = None
    shared_dataset_descriptor = ""
    if not args.use_xlsum:
        if not args.dataset:
            raise SystemExit("Either --dataset or --use-xlsum must be provided.")
        dataset_path = Path(args.dataset)
        if not dataset_path.exists():
            raise SystemExit(f"Dataset not found: {dataset_path}")
        shared_records = load_records(dataset_path)
        shared_dataset_descriptor = str(dataset_path.resolve())

    if args.output_dir:
        run_dir = Path(args.output_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = Path(__file__).resolve().parent / "eval_runs" / f"run_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    scorer = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True)

    detailed_rows: List[dict] = []
    dataset_descriptors: Dict[str, str] = {}
    sample_counts: Dict[str, int] = {}

    for language_key in selected_languages:
        if args.use_xlsum:
            xlsum_subset = resolve_xlsum_subset(language_key, args.xlsum_language)
            records = load_xlsum_records(
                language=xlsum_subset,
                split=args.xlsum_split,
                cache_dir=args.xlsum_cache_dir,
                shuffle_seed=args.xlsum_shuffle_seed,
            )
            dataset_descriptors[language_key] = (
                f"hf://csebuetnlp/xlsum/{xlsum_subset}/{args.xlsum_split}"
            )
        else:
            records = shared_records or []
            dataset_descriptors[language_key] = shared_dataset_descriptor

        local_args = copy.deepcopy(args)
        if args.use_xlsum:
            if local_args.article_field == "article":
                local_args.article_field = "text"
            if local_args.reference_field == "reference_summary":
                local_args.reference_field = "summary"
            if not local_args.title_field:
                local_args.title_field = "title"

        samples = prepare_samples(records, local_args)
        if not samples:
            raise SystemExit(
                f"No valid samples for language '{language_key}'. "
                "Check field names and dataset contents."
            )
        sample_counts[language_key] = len(samples)

        for model in selected_models:
            print(
                f"[INFO] Evaluating language={language_key} model={model} on {len(samples)} samples"
            )
            for idx, sample in enumerate(samples, start=1):
                start_t = time.perf_counter()
                generated = summarize_fn(sample["source_text"], model, language_key)
                latency = time.perf_counter() - start_t

                metrics = evaluate_sample(
                    source_text=sample["source_text"],
                    reference_summary=sample["reference_summary"],
                    generated_summary=generated,
                    latency_seconds=latency,
                    language_key=language_key,
                    scorer=scorer,
                )

                row = {
                    "sample_id": sample["sample_id"],
                    "model": model,
                    "language": language_key,
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
                    print(
                        f"[INFO] language={language_key} model={model} progress={idx}/{len(samples)}"
                    )

    aggregates = aggregate_model_metrics(detailed_rows)

    write_csv(run_dir / "detailed_metrics.csv", detailed_rows)
    write_csv(run_dir / "model_summary.csv", aggregates)

    config = {
        "dataset": dataset_descriptors,
        "dataset_mode": "xlsum" if args.use_xlsum else "file",
        "xlsum_language": args.xlsum_language if args.use_xlsum else "",
        "xlsum_split": args.xlsum_split if args.use_xlsum else "",
        "article_field": args.article_field,
        "reference_field": args.reference_field,
        "id_field": args.id_field,
        "title_field": args.title_field,
        "models": selected_models,
        "languages": selected_languages,
        "sample_count_by_language": sample_counts,
        "generated_at": datetime.now().isoformat(),
    }
    (run_dir / "run_config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report_text = build_report(aggregates)
    (run_dir / "report.md").write_text(report_text, encoding="utf-8")

    pdf_ready = generate_pdf_report(run_dir / "report.pdf", aggregates, config)
    if not pdf_ready:
        print(
            "[WARN] PDF report was skipped. Install reportlab to enable report.pdf generation.",
            file=sys.stderr,
        )

    print(f"[INFO] Evaluation completed. Outputs: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
