#!/usr/bin/env python3
"""Validate RSS/source pool health and article-body quality."""

import argparse
import json
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = SCRIPT_DIR.parent / "evaluation" / "source_validation_reports"


def parse_args():
    """Parse command-line arguments for source pool validation."""
    parser = argparse.ArgumentParser(description="Validate RSS and body quality across sources")
    parser.add_argument("--language", default="__all__", help="Language key or __all__")
    parser.add_argument("--topic", default="__all__", help="Topic filter or __all__")
    parser.add_argument("--max-sources", type=int, default=0, help="Max sources to test (0=all)")
    parser.add_argument("--sample-links", type=int, default=2, help="Articles sampled per source")
    parser.add_argument("--rss-limit", type=int, default=5, help="Entries to pull per source for sampling")
    parser.add_argument("--workers", type=int, default=8, help="Parallel workers")
    parser.add_argument("--min-article-chars", type=int, default=300, help="Min cleaned article length")
    parser.add_argument("--min-quality-score", type=float, default=120.0, help="Min score_article_candidate")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for report artifacts",
    )
    return parser.parse_args()


def load_runtime():
    """Import the application runtime and verify required validation helpers."""
    runtime = None
    import_error = None

    try:
        import core as runtime_module
        runtime = runtime_module
    except Exception as exc:  # pragma: no cover - environment dependent
        import_error = exc

    if runtime is None:
        try:
            import app as runtime_module
            runtime = runtime_module
        except Exception as exc:  # pragma: no cover - environment dependent
            import_error = exc

    if runtime is None:
        raise RuntimeError(
            "Unable to import runtime from core.py/app.py. Install runtime deps first (at least Flask)."
        ) from import_error

    required = [
        "NEWS_SOURCES",
        "fetch_source_news",
        "fetch_article_text",
        "clean_article_for_summarization",
        "score_article_candidate",
        "extractive_fallback",
        "is_degenerate_summary",
    ]
    missing = [name for name in required if not hasattr(runtime, name)]
    if missing:
        raise RuntimeError(f"Missing runtime members: {', '.join(missing)}")
    return runtime


def min_article_chars_for_language(base_min: int, language: str) -> int:
    """Return a language-adjusted minimum article length threshold."""
    language = (language or "").strip().lower()
    if language in {"ja", "ko", "zh"}:
        return max(180, int(base_min * 0.7))
    return base_min


def evaluate_source(runtime, source_key, source_cfg, args):
    """Evaluate one source for RSS availability and article-body quality."""
    language = source_cfg.get("language", "")
    topic = source_cfg.get("topic", "")
    rss_url = source_cfg.get("rss_url", "")

    result = {
        "source_key": source_key,
        "source_name": source_cfg.get("name", source_key),
        "language": language,
        "topic": topic,
        "country": source_cfg.get("country", ""),
        "region": source_cfg.get("region", ""),
        "rss_url": rss_url,
        "rss_ok": False,
        "rss_entries": 0,
        "samples_tested": 0,
        "article_success_count": 0,
        "article_success_ratio": 0.0,
        "avg_article_chars": 0.0,
        "avg_quality_score": 0.0,
        "summary_seed_success_ratio": 0.0,
        "pass": False,
        "reasons": [],
        "warnings": [],
    }

    try:
        entries = runtime.fetch_source_news(source_key, source_cfg, max(1, args.rss_limit))
    except Exception as exc:
        result["reasons"].append(f"rss_exception:{type(exc).__name__}")
        return result

    result["rss_entries"] = len(entries)
    result["rss_ok"] = len(entries) > 0
    if not result["rss_ok"]:
        result["reasons"].append("rss_no_entries")
        return result

    article_chars = []
    quality_scores = []
    summary_seed_ok = 0
    sample_count = 0
    min_article_chars = min_article_chars_for_language(args.min_article_chars, language)

    for entry in entries[: max(1, args.sample_links)]:
        sample_count += 1
        link = entry.get("link", "")
        title = entry.get("title", "")

        body = runtime.fetch_article_text(link, source_key=source_key)
        cleaned = runtime.clean_article_for_summarization(
            body,
            language,
            title=title,
            source_key=source_key,
            source_url=link,
        )
        cleaned_len = len(cleaned or "")

        score = runtime.score_article_candidate(cleaned) if cleaned else -10000.0
        article_chars.append(float(cleaned_len))
        quality_scores.append(float(score))

        summary_seed = runtime.extractive_fallback(cleaned, max_chars=320, avoid_text=title)
        seed_ok = bool(summary_seed) and not runtime.is_degenerate_summary(summary_seed)
        if seed_ok:
            summary_seed_ok += 1

        if cleaned_len >= min_article_chars and score >= args.min_quality_score:
            result["article_success_count"] += 1

    result["samples_tested"] = sample_count
    if sample_count > 0:
        result["article_success_ratio"] = result["article_success_count"] / sample_count
        result["summary_seed_success_ratio"] = summary_seed_ok / sample_count
    if article_chars:
        result["avg_article_chars"] = statistics.mean(article_chars)
    if quality_scores:
        result["avg_quality_score"] = statistics.mean(quality_scores)

    if result["article_success_ratio"] < 0.5:
        result["reasons"].append("body_quality_low")
    if result["summary_seed_success_ratio"] < 0.5:
        result["warnings"].append("summary_seed_low")

    result["pass"] = result["rss_ok"] and "body_quality_low" not in result["reasons"]
    return result


def render_markdown_report(results, args):
    """Render source validation results as a Markdown report."""
    total = len(results)
    passed = sum(1 for r in results if r["pass"])
    failed = total - passed

    lines = []
    lines.append("# Source Pool Validation Report")
    lines.append("")
    lines.append(f"- Generated at (UTC): {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"- Language filter: {args.language}")
    lines.append(f"- Topic filter: {args.topic}")
    lines.append(f"- Sources tested: {total}")
    lines.append(f"- Passed: {passed}")
    lines.append(f"- Failed: {failed}")
    lines.append("")

    if failed:
        lines.append("## Failed Sources")
        lines.append("")
        lines.append("| Language | Source | Topic | RSS | Body Success | Quality | Reasons |")
        lines.append("|---|---|---|---:|---:|---:|---|")
        for row in sorted((r for r in results if not r["pass"]), key=lambda x: (x["language"], x["source_key"])):
            lines.append(
                "| {language} | {source_name} (`{source_key}`) | {topic} | {rss_entries} | {article_success_ratio:.2f} | {avg_quality_score:.1f} | {reasons} |".format(
                    language=row["language"],
                    source_name=row["source_name"],
                    source_key=row["source_key"],
                    topic=row["topic"],
                    rss_entries=row["rss_entries"],
                    article_success_ratio=row["article_success_ratio"],
                    avg_quality_score=row["avg_quality_score"],
                    reasons=", ".join(row["reasons"]),
                )
            )
        lines.append("")

    lines.append("## Top Quality Sources")
    lines.append("")
    lines.append("| Language | Source | Topic | Avg Chars | Avg Score | Body Success |")
    lines.append("|---|---|---|---:|---:|---:|")
    ranked = sorted(
        results,
        key=lambda x: (x["pass"], x["article_success_ratio"], x["avg_quality_score"], x["avg_article_chars"]),
        reverse=True,
    )
    for row in ranked[:25]:
        lines.append(
            "| {language} | {source_name} (`{source_key}`) | {topic} | {avg_article_chars:.0f} | {avg_quality_score:.1f} | {article_success_ratio:.2f} |".format(
                language=row["language"],
                source_name=row["source_name"],
                source_key=row["source_key"],
                topic=row["topic"],
                avg_article_chars=row["avg_article_chars"],
                avg_quality_score=row["avg_quality_score"],
                article_success_ratio=row["article_success_ratio"],
            )
        )
    lines.append("")

    return "\n".join(lines)


def main():
    """Run source validation and write JSON and Markdown report artifacts."""
    args = parse_args()
    runtime = load_runtime()

    all_sources = runtime.NEWS_SOURCES
    source_items = []
    for key, cfg in all_sources.items():
        if args.language not in {"", "__all__"} and cfg.get("language") != args.language:
            continue
        if args.topic not in {"", "__all__"} and cfg.get("topic") != args.topic:
            continue
        source_items.append((key, cfg))

    source_items.sort(key=lambda x: (x[1].get("language", ""), x[1].get("topic", ""), x[0]))
    if args.max_sources and args.max_sources > 0:
        source_items = source_items[: args.max_sources]

    results = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(evaluate_source, runtime, key, cfg, args): (key, cfg)
            for key, cfg in source_items
        }
        for future in as_completed(futures):
            results.append(future.result())

    results.sort(key=lambda x: (x["language"], x["topic"], x["source_key"]))

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"source_validation_{stamp}.json"
    md_path = out_dir / f"source_validation_{stamp}.md"

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "args": vars(args),
        "summary": {
            "tested": len(results),
            "passed": sum(1 for r in results if r["pass"]),
            "failed": sum(1 for r in results if not r["pass"]),
        },
        "results": results,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown_report(results, args), encoding="utf-8")

    print(f"tested={payload['summary']['tested']} passed={payload['summary']['passed']} failed={payload['summary']['failed']}")
    print(f"json_report={json_path}")
    print(f"md_report={md_path}")


if __name__ == "__main__":
    main()
