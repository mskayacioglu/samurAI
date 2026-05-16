#!/usr/bin/env python3
"""Generate a rich visualization set from XL-Sum evaluation CSV files.

The script scans evaluation run directories that contain:
  - model_overall_macro_summary.csv
  - model_language_summary.csv
  - detailed_metrics.csv

It intentionally ignores virtualenv/dependency CSV files and writes all outputs
under a separate visualization directory.
"""

from __future__ import annotations

import argparse
import math
import os
import re
import shutil
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

MPL_CACHE_DIR = Path(__file__).resolve().parent / ".matplotlib_cache"
LOCAL_CACHE_DIR = Path(__file__).resolve().parent / ".cache"
MPL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
LOCAL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CACHE_DIR))
os.environ.setdefault("XDG_CACHE_HOME", str(LOCAL_CACHE_DIR))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

try:
    import plotly.express as px
except Exception:  # pragma: no cover - optional dependency
    px = None


warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)


MODEL_ORDER = ["mt5-xlsum", "mbart50_xlsum", "mbart-xlsum-2"]
MODEL_LABELS = {
    "mt5-xlsum": "mT5 XL-Sum (hazir)",
    "mbart50_xlsum": "mBART50 (egitilen)",
    "mbart-xlsum-2": "mBART-2 (egitilen)",
}
MODEL_PALETTE = {
    "mt5-xlsum": "#3b6fb6",
    "mbart50_xlsum": "#d95f02",
    "mbart-xlsum-2": "#1b9e77",
}

LANGUAGE_NAMES = {
    "ar": "Arapca",
    "en": "Ingilizce",
    "es": "Ispanyolca",
    "fr": "Fransizca",
    "hi": "Hintce",
    "ja": "Japonca",
    "ko": "Korece",
    "ru": "Rusca",
    "tr": "Turkce",
    "vi": "Vietnamca",
    "zh": "Cince",
}

HIGHER_IS_BETTER = {
    "latency_seconds": False,
    "latency_per_1k_tokens": False,
    "latency_seconds_mean": False,
    "latency_per_1k_tokens_mean": False,
    "repetition_3gram": False,
    "repetition_3gram_mean": False,
}

OVERALL_GROUPS = {
    "classical": [
        "rouge1_fmeasure_mean",
        "rouge2_fmeasure_mean",
        "rougeL_fmeasure_mean",
        "bleu_mean",
        "meteor_lite_mean",
    ],
    "capability": [
        "capability_coherence_mean",
        "capability_accuracy_mean",
        "capability_clarity_mean",
        "capability_relevance_mean",
        "capability_efficiency_mean",
        "capability_overall_mean",
    ],
    "quality_grounding": [
        "quality_factuality_mean",
        "quality_completeness_mean",
        "source_coverage_mean",
        "source_recall_mean",
        "fragment_coverage_mean",
        "fragment_density_mean",
    ],
    "behavior_efficiency": [
        "latency_seconds_mean",
        "latency_per_1k_tokens_mean",
        "compression_ratio_mean",
        "novelty_1gram_mean",
        "novelty_2gram_mean",
        "repetition_3gram_mean",
        "summary_tokens_mean",
        "source_tokens_mean",
    ],
}

LANGUAGE_HEATMAP_METRICS = [
    "capability_overall_mean",
    "capability_coherence_mean",
    "capability_accuracy_mean",
    "capability_clarity_mean",
    "capability_relevance_mean",
    "capability_efficiency_mean",
    "rouge1_fmeasure_mean",
    "rouge2_fmeasure_mean",
    "rougeL_fmeasure_mean",
    "bleu_mean",
    "meteor_lite_mean",
    "quality_factuality_mean",
    "quality_completeness_mean",
    "source_coverage_mean",
    "source_recall_mean",
    "fragment_coverage_mean",
    "fragment_density_mean",
    "latency_seconds_mean",
    "latency_per_1k_tokens_mean",
    "compression_ratio_mean",
    "novelty_1gram_mean",
    "novelty_2gram_mean",
    "repetition_3gram_mean",
    "summary_tokens_mean",
]

DETAILED_KEY_METRICS = [
    "capability_overall",
    "capability_coherence",
    "capability_accuracy",
    "capability_clarity",
    "capability_relevance",
    "capability_efficiency",
    "rouge1_fmeasure",
    "rouge2_fmeasure",
    "rougeL_fmeasure",
    "bleu",
    "meteor_lite",
    "quality_factuality",
    "quality_completeness",
    "source_coverage",
    "source_recall",
    "fragment_coverage",
    "fragment_density",
    "novelty_1gram",
    "novelty_2gram",
    "repetition_3gram",
    "compression_ratio",
    "latency_seconds",
    "latency_per_1k_tokens",
    "summary_tokens",
    "source_tokens",
]

SCATTER_PAIRS = [
    ("source_tokens", "latency_seconds", "Kaynak uzunlugu ve uretim suresi"),
    ("source_tokens", "summary_tokens", "Kaynak ve ozet uzunlugu"),
    ("compression_ratio", "capability_overall", "Sikistirma ve genel kabiliyet"),
    ("compression_ratio", "rougeL_fmeasure", "Sikistirma ve ROUGE-L"),
    ("latency_per_1k_tokens", "capability_efficiency", "Normalize gecikme ve verimlilik"),
    ("source_coverage", "quality_factuality", "Kaynak kapsama ve factuality proxy"),
    ("source_recall", "capability_relevance", "Kaynak recall ve relevance proxy"),
    ("rougeL_fmeasure", "capability_accuracy", "ROUGE-L ve accuracy proxy"),
    ("repetition_3gram", "capability_clarity", "Tekrar ve clarity proxy"),
    ("novelty_2gram", "rougeL_fmeasure", "Novelty ve ROUGE-L"),
    ("fragment_density", "novelty_2gram", "Ekstraktiflik ve novelty"),
    ("summary_tokens", "quality_completeness", "Ozet uzunlugu ve completeness proxy"),
]

PAIRWISE_METRICS = [
    "capability_overall",
    "rougeL_fmeasure",
    "bleu",
    "meteor_lite",
    "capability_efficiency",
    "quality_factuality",
    "quality_completeness",
    "latency_seconds",
]

TEXT_COLUMNS = {"title", "source_text", "reference_summary", "generated_summary"}


@dataclass(frozen=True)
class EvalRun:
    name: str
    path: Path
    overall_csv: Path
    language_csv: Path
    detailed_csv: Path


class Manifest:
    def __init__(self) -> None:
        self.rows: list[dict[str, str]] = []

    def add(self, run: str, category: str, path: Path, title: str, description: str) -> None:
        self.rows.append(
            {
                "run": run,
                "category": category,
                "path": str(path),
                "title": title,
                "description": description,
            }
        )

    def write(self, out_dir: Path) -> None:
        df = pd.DataFrame(self.rows)
        df.to_csv(out_dir / "visualization_manifest.csv", index=False)
        lines = ["# Evaluation Visualization Index", ""]
        for run, run_df in df.groupby("run", sort=False):
            lines.extend([f"## {run}", ""])
            for category, cat_df in run_df.groupby("category", sort=False):
                lines.extend([f"### {category}", ""])
                for _, row in cat_df.iterrows():
                    rel = Path(row["path"]).relative_to(out_dir)
                    lines.append(f"- [{row['title']}]({rel}) - {row['description']}")
                lines.append("")
        (out_dir / "visualization_index.md").write_text("\n".join(lines), encoding="utf-8")


def metric_label(metric: str) -> str:
    label = metric
    for suffix in ("_mean", "_std", "_fmeasure"):
        label = label.replace(suffix, "")
    replacements = {
        "rouge1": "ROUGE-1",
        "rouge2": "ROUGE-2",
        "rougeL": "ROUGE-L",
        "bleu": "BLEU",
        "meteor_lite": "METEOR-lite",
        "capability": "Cap.",
        "quality": "Quality",
        "source": "Source",
        "fragment": "Fragment",
        "latency": "Latency",
        "compression": "Compression",
        "novelty": "Novelty",
        "repetition": "Repetition",
        "summary_tokens": "Summary tokens",
        "source_tokens": "Source tokens",
    }
    for old, new in replacements.items():
        label = label.replace(old, new)
    return label.replace("_", " ").title()


def model_order(values: Iterable[str]) -> list[str]:
    seen = list(dict.fromkeys(values))
    ordered = [m for m in MODEL_ORDER if m in seen]
    ordered.extend([m for m in seen if m not in ordered])
    return ordered


def language_order(values: Iterable[str]) -> list[str]:
    return sorted(dict.fromkeys(values), key=lambda x: (x != "tr", x))


def clean_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return value.strip("_").lower()


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_figure(fig: plt.Figure, out_path: Path, manifest: Manifest, run: str, category: str, title: str, description: str) -> None:
    ensure_dir(out_path.parent)
    fig.savefig(out_path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    manifest.add(run, category, out_path, title, description)


def write_html(path: Path, html: str, manifest: Manifest, run: str, category: str, title: str, description: str) -> None:
    ensure_dir(path.parent)
    path.write_text(html, encoding="utf-8")
    manifest.add(run, category, path, title, description)


def discover_runs(input_root: Path) -> list[EvalRun]:
    ignored = {".venv", ".venv_broken_20260329_173249", "__pycache__", "visualizations", "eval_visualizations"}
    runs: list[EvalRun] = []
    for directory in sorted([p for p in input_root.rglob("*") if p.is_dir()]):
        if any(part in ignored for part in directory.parts):
            continue
        overall = directory / "model_overall_macro_summary.csv"
        language = directory / "model_language_summary.csv"
        detailed = directory / "detailed_metrics.csv"
        if overall.exists() and language.exists() and detailed.exists():
            runs.append(EvalRun(directory.name, directory, overall, language, detailed))
    return runs


def read_overall(run: EvalRun) -> pd.DataFrame:
    df = pd.read_csv(run.overall_csv)
    df["model"] = pd.Categorical(df["model"], categories=model_order(df["model"]), ordered=True)
    return df.sort_values("model")


def read_language(run: EvalRun) -> pd.DataFrame:
    df = pd.read_csv(run.language_csv)
    df["model"] = pd.Categorical(df["model"], categories=model_order(df["model"]), ordered=True)
    df["language"] = pd.Categorical(df["language"], categories=language_order(df["language"]), ordered=True)
    return df.sort_values(["language", "model"])


def detailed_usecols(path: Path) -> list[str]:
    cols = list(pd.read_csv(path, nrows=0).columns)
    return [c for c in cols if c not in TEXT_COLUMNS]


def read_detailed(run: EvalRun) -> pd.DataFrame:
    df = pd.read_csv(run.detailed_csv, usecols=detailed_usecols(run.detailed_csv), low_memory=False)
    df["model"] = pd.Categorical(df["model"], categories=model_order(df["model"]), ordered=True)
    df["language"] = pd.Categorical(df["language"], categories=language_order(df["language"]), ordered=True)
    numeric_cols = [c for c in df.columns if c not in {"run_name", "model", "model_scope", "model_family", "language", "xlsum_subset", "split", "sample_id"}]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def sample_df(df: pd.DataFrame, sample_size: int, seed: int = 42) -> pd.DataFrame:
    if len(df) <= sample_size:
        return df
    return df.sample(sample_size, random_state=seed)


def add_value_labels(ax: plt.Axes, fmt: str = "{:.3f}", rotation: int = 0) -> None:
    for container in ax.containers:
        try:
            ax.bar_label(container, fmt=fmt, fontsize=8, rotation=rotation, padding=2)
        except Exception:
            continue


def plot_overall_grouped_bars(run: EvalRun, overall: pd.DataFrame, out_dir: Path, manifest: Manifest) -> None:
    for group_name, metrics in OVERALL_GROUPS.items():
        present = [m for m in metrics if m in overall.columns]
        if not present:
            continue
        plot_df = overall.melt(id_vars="model", value_vars=present, var_name="metric", value_name="value")
        plot_df["metric_label"] = plot_df["metric"].map(metric_label)
        width = max(11, len(present) * 1.15)
        fig, ax = plt.subplots(figsize=(width, 6))
        sns.barplot(data=plot_df, x="metric_label", y="value", hue="model", hue_order=model_order(overall["model"].astype(str)), palette=MODEL_PALETTE, ax=ax)
        ax.set_title(f"{run.name}: {group_name} metrikleri - model karsilastirmasi", fontsize=14, weight="bold")
        ax.set_xlabel("")
        ax.set_ylabel("Ortalama deger")
        ax.tick_params(axis="x", rotation=35)
        ax.legend(title="Model", loc="best")
        ax.grid(axis="y", alpha=0.25)
        save_figure(
            fig,
            out_dir / run.name / "01_overall" / f"overall_grouped_bar_{group_name}.png",
            manifest,
            run.name,
            "overall",
            f"{group_name} grouped bar",
            "Overall macro summary uzerinden model bazli gruplanmis metrik cubuk grafigi.",
        )


def plot_overall_heatmaps(run: EvalRun, overall: pd.DataFrame, out_dir: Path, manifest: Manifest) -> None:
    metrics = [m for group in OVERALL_GROUPS.values() for m in group if m in overall.columns]
    data = overall.set_index("model")[metrics].T
    fig, ax = plt.subplots(figsize=(8, max(8, len(metrics) * 0.33)))
    sns.heatmap(data, annot=True, fmt=".3f", cmap="viridis", linewidths=0.4, ax=ax)
    ax.set_title(f"{run.name}: genel metrik matrisi", fontsize=14, weight="bold")
    ax.set_xlabel("Model")
    ax.set_ylabel("Metrik")
    ax.set_yticklabels([metric_label(m) for m in metrics])
    save_figure(
        fig,
        out_dir / run.name / "01_overall" / "overall_metric_heatmap.png",
        manifest,
        run.name,
        "overall",
        "Overall metric heatmap",
        "Tum makro metriklerin model bazli isiya donusturulmus gorunumu.",
    )

    rank_df = data.copy()
    for metric in rank_df.index:
        ascending = not HIGHER_IS_BETTER.get(metric, True)
        rank_df.loc[metric] = rank_df.loc[metric].rank(ascending=ascending, method="min")
    fig, ax = plt.subplots(figsize=(7, max(8, len(metrics) * 0.33)))
    sns.heatmap(rank_df, annot=True, fmt=".0f", cmap="YlGnBu_r", linewidths=0.4, cbar_kws={"label": "Rank (1 en iyi)"}, ax=ax)
    ax.set_title(f"{run.name}: metrik bazli model siralari", fontsize=14, weight="bold")
    ax.set_xlabel("Model")
    ax.set_ylabel("Metrik")
    ax.set_yticklabels([metric_label(m) for m in metrics])
    save_figure(
        fig,
        out_dir / run.name / "01_overall" / "overall_rank_heatmap.png",
        manifest,
        run.name,
        "overall",
        "Overall rank heatmap",
        "Her metrik icin model siralamalarini gosterir; 1 en iyi skordur.",
    )


def plot_radar(run: EvalRun, overall: pd.DataFrame, metrics: list[str], filename: str, title: str, out_dir: Path, manifest: Manifest) -> None:
    metrics = [m for m in metrics if m in overall.columns]
    if len(metrics) < 3:
        return
    angles = np.linspace(0, 2 * np.pi, len(metrics), endpoint=False).tolist()
    angles += angles[:1]
    fig = plt.figure(figsize=(8, 8))
    ax = fig.add_subplot(111, polar=True)
    for _, row in overall.iterrows():
        values = [float(row[m]) for m in metrics]
        values += values[:1]
        model = str(row["model"])
        ax.plot(angles, values, linewidth=2.2, label=model, color=MODEL_PALETTE.get(model))
        ax.fill(angles, values, alpha=0.10, color=MODEL_PALETTE.get(model))
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels([metric_label(m) for m in metrics], fontsize=9)
    ax.set_ylim(0, max(1.0, overall[metrics].max().max() * 1.05))
    ax.set_title(f"{run.name}: {title}", fontsize=14, weight="bold", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.15))
    ax.grid(alpha=0.35)
    save_figure(
        fig,
        out_dir / run.name / "01_overall" / filename,
        manifest,
        run.name,
        "overall",
        title,
        "Model profillerini radar grafikte karsilastirir.",
    )


def plot_overall_tradeoffs(run: EvalRun, overall: pd.DataFrame, out_dir: Path, manifest: Manifest) -> None:
    pairs = [
        ("latency_seconds_mean", "capability_overall_mean", "Gecikme vs genel kabiliyet"),
        ("compression_ratio_mean", "quality_completeness_mean", "Sikistirma vs completeness"),
        ("source_coverage_mean", "quality_factuality_mean", "Kaynak kapsama vs factuality"),
        ("capability_efficiency_mean", "rougeL_fmeasure_mean", "Verimlilik vs ROUGE-L"),
    ]
    for x, y, title in pairs:
        if x not in overall.columns or y not in overall.columns:
            continue
        fig, ax = plt.subplots(figsize=(8, 6))
        for _, row in overall.iterrows():
            model = str(row["model"])
            ax.scatter(row[x], row[y], s=220, color=MODEL_PALETTE.get(model), edgecolor="white", linewidth=1.2)
            ax.annotate(model, (row[x], row[y]), xytext=(8, 8), textcoords="offset points", fontsize=9)
        ax.set_title(f"{run.name}: {title}", fontsize=14, weight="bold")
        ax.set_xlabel(metric_label(x))
        ax.set_ylabel(metric_label(y))
        ax.grid(alpha=0.25)
        save_figure(
            fig,
            out_dir / run.name / "01_overall" / f"overall_tradeoff_{clean_name(x)}__{clean_name(y)}.png",
            manifest,
            run.name,
            "overall",
            title,
            "Makro seviyede iki metrik arasindaki model trade-off'unu gosterir.",
        )


def plot_language_heatmaps(run: EvalRun, language: pd.DataFrame, out_dir: Path, manifest: Manifest) -> None:
    for metric in [m for m in LANGUAGE_HEATMAP_METRICS if m in language.columns]:
        pivot = language.pivot(index="language", columns="model", values=metric)
        fig, ax = plt.subplots(figsize=(7.2, 7.2))
        cmap = "mako_r" if not HIGHER_IS_BETTER.get(metric, True) else "viridis"
        sns.heatmap(pivot, annot=True, fmt=".3f", cmap=cmap, linewidths=0.5, ax=ax)
        ax.set_title(f"{run.name}: dil-model {metric_label(metric)}", fontsize=14, weight="bold")
        ax.set_xlabel("Model")
        ax.set_ylabel("Dil")
        ax.set_yticklabels([LANGUAGE_NAMES.get(str(t.get_text()), str(t.get_text())) for t in ax.get_yticklabels()], rotation=0)
        save_figure(
            fig,
            out_dir / run.name / "02_language_summary" / "metric_heatmaps" / f"language_model_heatmap_{clean_name(metric)}.png",
            manifest,
            run.name,
            "language_summary",
            f"{metric_label(metric)} heatmap",
            "Dil x model matrisinde ilgili metrik ortalamalari.",
        )


def plot_language_deltas(run: EvalRun, language: pd.DataFrame, out_dir: Path, manifest: Manifest) -> None:
    pairs = [("mt5-xlsum", "mbart50_xlsum"), ("mt5-xlsum", "mbart-xlsum-2"), ("mbart50_xlsum", "mbart-xlsum-2")]
    metrics = [m for m in LANGUAGE_HEATMAP_METRICS if m in language.columns and m.endswith("_mean")]
    for left, right in pairs:
        if left not in language["model"].astype(str).unique() or right not in language["model"].astype(str).unique():
            continue
        rows = []
        for metric in metrics:
            pivot = language.pivot(index="language", columns="model", values=metric)
            if left in pivot.columns and right in pivot.columns:
                diff = pivot[left] - pivot[right]
                for lang, value in diff.items():
                    rows.append({"language": lang, "metric": metric, "delta": value})
        if not rows:
            continue
        delta = pd.DataFrame(rows)
        mat = delta.pivot(index="metric", columns="language", values="delta")
        fig, ax = plt.subplots(figsize=(12, max(8, len(metrics) * 0.28)))
        lim = np.nanmax(np.abs(mat.to_numpy()))
        sns.heatmap(mat, cmap="vlag", center=0, vmin=-lim, vmax=lim, linewidths=0.3, ax=ax)
        ax.set_title(f"{run.name}: {left} eksi {right} dil-metrik farklari", fontsize=14, weight="bold")
        ax.set_xlabel("Dil")
        ax.set_ylabel("Metrik")
        ax.set_yticklabels([metric_label(m) for m in mat.index])
        save_figure(
            fig,
            out_dir / run.name / "02_language_summary" / "pairwise_deltas" / f"language_metric_delta_{clean_name(left)}_minus_{clean_name(right)}.png",
            manifest,
            run.name,
            "language_summary",
            f"{left} - {right} metric deltas",
            "Dil ve metrik bazinda iki model arasindaki ortalama skor farklari.",
        )


def plot_language_rank_and_winners(run: EvalRun, language: pd.DataFrame, out_dir: Path, manifest: Manifest) -> None:
    metric = "capability_overall_mean"
    if metric not in language.columns:
        return
    pivot = language.pivot(index="language", columns="model", values=metric)
    rank = pivot.rank(axis=1, ascending=False, method="min")
    fig, ax = plt.subplots(figsize=(7.2, 7.2))
    sns.heatmap(rank, annot=True, fmt=".0f", cmap="YlGnBu_r", linewidths=0.5, cbar_kws={"label": "Rank (1 en iyi)"}, ax=ax)
    ax.set_title(f"{run.name}: dil bazli capability siralamasi", fontsize=14, weight="bold")
    ax.set_xlabel("Model")
    ax.set_ylabel("Dil")
    save_figure(
        fig,
        out_dir / run.name / "02_language_summary" / "language_capability_rank_heatmap.png",
        manifest,
        run.name,
        "language_summary",
        "Language capability rank heatmap",
        "Her dilde capability_overall_mean icin model siralamasi.",
    )

    winners = pivot.idxmax(axis=1).rename("winner").reset_index()
    winners["language_label"] = winners["language"].astype(str).map(lambda x: LANGUAGE_NAMES.get(x, x))
    fig, ax = plt.subplots(figsize=(10, 5.5))
    sns.countplot(data=winners, x="winner", order=model_order(winners["winner"]), palette=MODEL_PALETTE, ax=ax)
    add_value_labels(ax, fmt="{:.0f}")
    ax.set_title(f"{run.name}: dil kazanma sayilari", fontsize=14, weight="bold")
    ax.set_xlabel("Kazanan model")
    ax.set_ylabel("Dil sayisi")
    ax.grid(axis="y", alpha=0.25)
    save_figure(
        fig,
        out_dir / run.name / "02_language_summary" / "language_winner_counts.png",
        manifest,
        run.name,
        "language_summary",
        "Language winner counts",
        "Capability overall bazinda kac dilde hangi modelin birinci oldugu.",
    )

    sorted_langs = pivot.mean(axis=1).sort_values(ascending=False).index
    plot_df = language[language["language"].isin(sorted_langs)].copy()
    plot_df["language"] = pd.Categorical(plot_df["language"], categories=list(sorted_langs), ordered=True)
    fig, ax = plt.subplots(figsize=(12, 6))
    sns.lineplot(data=plot_df.sort_values("language"), x="language", y=metric, hue="model", marker="o", palette=MODEL_PALETTE, ax=ax)
    ax.set_title(f"{run.name}: diller boyunca capability profili", fontsize=14, weight="bold")
    ax.set_xlabel("Dil")
    ax.set_ylabel("Capability overall mean")
    ax.grid(axis="y", alpha=0.25)
    save_figure(
        fig,
        out_dir / run.name / "02_language_summary" / "language_capability_profile_lines.png",
        manifest,
        run.name,
        "language_summary",
        "Language capability profile lines",
        "Modellerin diller boyunca genel kabiliyet profilini gosterir.",
    )


def plot_language_metric_small_multiples(run: EvalRun, language: pd.DataFrame, out_dir: Path, manifest: Manifest) -> None:
    metric_sets = {
        "classical": [m for m in OVERALL_GROUPS["classical"] if m in language.columns],
        "capability": [m for m in OVERALL_GROUPS["capability"] if m in language.columns],
        "quality": [m for m in OVERALL_GROUPS["quality_grounding"] if m in language.columns],
    }
    for group, metrics in metric_sets.items():
        if not metrics:
            continue
        ncols = 2
        nrows = math.ceil(len(metrics) / ncols)
        fig, axes = plt.subplots(nrows, ncols, figsize=(15, 4.3 * nrows), squeeze=False)
        for ax, metric in zip(axes.ravel(), metrics):
            sns.lineplot(data=language, x="language", y=metric, hue="model", marker="o", palette=MODEL_PALETTE, ax=ax, legend=False)
            ax.set_title(metric_label(metric), fontsize=11, weight="bold")
            ax.set_xlabel("")
            ax.set_ylabel("")
            ax.tick_params(axis="x", rotation=35)
            ax.grid(axis="y", alpha=0.2)
        for ax in axes.ravel()[len(metrics) :]:
            ax.axis("off")
        handles, labels = axes[0][0].get_legend_handles_labels()
        fig.legend(handles, labels, loc="upper center", ncol=3, title="Model")
        fig.suptitle(f"{run.name}: dil bazli {group} metrik profilleri", fontsize=16, weight="bold", y=1.01)
        fig.tight_layout()
        save_figure(
            fig,
            out_dir / run.name / "02_language_summary" / f"language_small_multiples_{group}.png",
            manifest,
            run.name,
            "language_summary",
            f"Language {group} small multiples",
            "Ayni metrik grubundaki dil bazli model profillerini kucuk coklu grafiklerle gosterir.",
        )


def plot_samples_by_language(run: EvalRun, language: pd.DataFrame, out_dir: Path, manifest: Manifest) -> None:
    if "samples" not in language.columns:
        return
    sample_df = language.drop_duplicates("language")[["language", "samples"]].sort_values("samples", ascending=False)
    fig, ax = plt.subplots(figsize=(10, 5.5))
    sns.barplot(data=sample_df, x="language", y="samples", color="#4c78a8", ax=ax)
    add_value_labels(ax, fmt="{:.0f}", rotation=90)
    ax.set_title(f"{run.name}: dil bazli ornek sayilari", fontsize=14, weight="bold")
    ax.set_xlabel("Dil")
    ax.set_ylabel("Ornek sayisi")
    ax.grid(axis="y", alpha=0.25)
    save_figure(
        fig,
        out_dir / run.name / "02_language_summary" / "language_sample_counts.png",
        manifest,
        run.name,
        "language_summary",
        "Language sample counts",
        "Her dil icin degerlendirme ornek sayisi.",
    )


def plot_detailed_distributions(run: EvalRun, detailed: pd.DataFrame, out_dir: Path, manifest: Manifest, sample_size: int) -> None:
    sample = sample_df(detailed, sample_size)
    metrics = [m for m in DETAILED_KEY_METRICS if m in sample.columns]
    core_metrics = [
        "capability_overall",
        "rougeL_fmeasure",
        "bleu",
        "meteor_lite",
        "quality_factuality",
        "quality_completeness",
        "compression_ratio",
        "latency_seconds",
        "repetition_3gram",
    ]
    for metric in [m for m in core_metrics if m in metrics]:
        fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
        sns.violinplot(data=sample, x="model", y=metric, order=model_order(sample["model"].astype(str)), palette=MODEL_PALETTE, inner="quartile", cut=0, ax=axes[0])
        axes[0].set_title("Model dagilimi", weight="bold")
        axes[0].set_xlabel("")
        axes[0].set_ylabel(metric_label(metric))
        axes[0].tick_params(axis="x", rotation=15)
        sns.boxplot(data=sample, x="language", y=metric, hue="model", palette=MODEL_PALETTE, fliersize=0.5, linewidth=0.8, ax=axes[1])
        axes[1].set_title("Dil x model dagilimi", weight="bold")
        axes[1].set_xlabel("Dil")
        axes[1].set_ylabel("")
        axes[1].tick_params(axis="x", rotation=35)
        axes[1].legend(title="Model", fontsize=8)
        fig.suptitle(f"{run.name}: {metric_label(metric)} dagilimlari", fontsize=15, weight="bold")
        fig.tight_layout()
        save_figure(
            fig,
            out_dir / run.name / "03_detailed_distributions" / f"distribution_{clean_name(metric)}.png",
            manifest,
            run.name,
            "detailed_distributions",
            f"{metric_label(metric)} distributions",
            "Detailed metrics seviyesinde model ve dil bazli dagilimlar.",
        )

        fig, ax = plt.subplots(figsize=(10, 5.5))
        sns.ecdfplot(data=sample, x=metric, hue="model", hue_order=model_order(sample["model"].astype(str)), palette=MODEL_PALETTE, ax=ax)
        ax.set_title(f"{run.name}: {metric_label(metric)} ECDF", fontsize=14, weight="bold")
        ax.set_xlabel(metric_label(metric))
        ax.set_ylabel("Kumulatif oran")
        ax.grid(alpha=0.25)
        save_figure(
            fig,
            out_dir / run.name / "03_detailed_distributions" / f"ecdf_{clean_name(metric)}.png",
            manifest,
            run.name,
            "detailed_distributions",
            f"{metric_label(metric)} ECDF",
            "Model dagilimlarini kumulatif olarak karsilastirir.",
        )

    long = sample.melt(id_vars=["model", "language"], value_vars=metrics, var_name="metric", value_name="value").dropna()
    stats = long.groupby(["metric", "model"], observed=True)["value"].agg(["mean", "median", "std"]).reset_index()
    for stat in ["mean", "median", "std"]:
        pivot = stats.pivot(index="metric", columns="model", values=stat)
        fig, ax = plt.subplots(figsize=(8, max(8, len(metrics) * 0.27)))
        sns.heatmap(pivot, annot=True, fmt=".3f", cmap="viridis", linewidths=0.3, ax=ax)
        ax.set_title(f"{run.name}: detailed {stat} ozeti", fontsize=14, weight="bold")
        ax.set_xlabel("Model")
        ax.set_ylabel("Metrik")
        ax.set_yticklabels([metric_label(m) for m in pivot.index])
        save_figure(
            fig,
            out_dir / run.name / "03_detailed_distributions" / f"detailed_metric_{stat}_heatmap.png",
            manifest,
            run.name,
            "detailed_distributions",
            f"Detailed metric {stat} heatmap",
            "Detailed metrics uzerinden model bazli ozet istatistik matrisi.",
        )


def plot_detailed_correlations(run: EvalRun, detailed: pd.DataFrame, out_dir: Path, manifest: Manifest, sample_size: int) -> None:
    sample = sample_df(detailed, sample_size)
    metrics = [m for m in DETAILED_KEY_METRICS if m in sample.columns]
    corr = sample[metrics].corr(numeric_only=True)
    fig, ax = plt.subplots(figsize=(14, 12))
    sns.heatmap(corr, cmap="vlag", center=0, linewidths=0.25, ax=ax)
    ax.set_title(f"{run.name}: metrik korelasyon matrisi", fontsize=15, weight="bold")
    ax.set_xticklabels([metric_label(t.get_text()) for t in ax.get_xticklabels()], rotation=45, ha="right")
    ax.set_yticklabels([metric_label(t.get_text()) for t in ax.get_yticklabels()], rotation=0)
    save_figure(
        fig,
        out_dir / run.name / "03_detailed_distributions" / "correlation_all_metrics.png",
        manifest,
        run.name,
        "detailed_distributions",
        "All metric correlation heatmap",
        "Detailed seviyedeki sayisal metriklerin korelasyon haritasi.",
    )

    for model in model_order(sample["model"].astype(str)):
        model_df = sample[sample["model"].astype(str) == model]
        if len(model_df) < 10:
            continue
        corr = model_df[metrics].corr(numeric_only=True)
        fig, ax = plt.subplots(figsize=(14, 12))
        sns.heatmap(corr, cmap="vlag", center=0, linewidths=0.25, ax=ax)
        ax.set_title(f"{run.name}: {model} metrik korelasyonlari", fontsize=15, weight="bold")
        ax.set_xticklabels([metric_label(t.get_text()) for t in ax.get_xticklabels()], rotation=45, ha="right")
        ax.set_yticklabels([metric_label(t.get_text()) for t in ax.get_yticklabels()], rotation=0)
        save_figure(
            fig,
            out_dir / run.name / "03_detailed_distributions" / "correlations_by_model" / f"correlation_{clean_name(model)}.png",
            manifest,
            run.name,
            "detailed_distributions",
            f"{model} correlation heatmap",
            "Tek model icin detailed metrik korelasyonlari.",
        )


def plot_detailed_scatter(run: EvalRun, detailed: pd.DataFrame, out_dir: Path, manifest: Manifest, sample_size: int) -> None:
    sample = sample_df(detailed, sample_size)
    for x, y, title in SCATTER_PAIRS:
        if x not in sample.columns or y not in sample.columns:
            continue
        fig, axes = plt.subplots(1, 2, figsize=(15, 5.8))
        sns.scatterplot(
            data=sample,
            x=x,
            y=y,
            hue="model",
            hue_order=model_order(sample["model"].astype(str)),
            palette=MODEL_PALETTE,
            alpha=0.32,
            linewidth=0,
            s=18,
            ax=axes[0],
        )
        axes[0].set_title("Model renkli scatter", weight="bold")
        axes[0].set_xlabel(metric_label(x))
        axes[0].set_ylabel(metric_label(y))
        axes[0].grid(alpha=0.2)
        axes[0].legend(title="Model", fontsize=8)

        hb = axes[1].hexbin(sample[x], sample[y], gridsize=45, mincnt=1, cmap="magma", bins="log")
        axes[1].set_title("Yogunluk hexbin", weight="bold")
        axes[1].set_xlabel(metric_label(x))
        axes[1].set_ylabel(metric_label(y))
        fig.colorbar(hb, ax=axes[1], label="log(count)")
        fig.suptitle(f"{run.name}: {title}", fontsize=15, weight="bold")
        fig.tight_layout()
        save_figure(
            fig,
            out_dir / run.name / "04_tradeoffs_scatter" / f"scatter_hexbin_{clean_name(x)}__{clean_name(y)}.png",
            manifest,
            run.name,
            "tradeoffs_scatter",
            title,
            "Detailed sample seviyesinde scatter ve yogunluk gorunumu.",
        )


def plot_pairplot(run: EvalRun, detailed: pd.DataFrame, out_dir: Path, manifest: Manifest, sample_size: int) -> None:
    if len(detailed) == 0:
        return
    cols = [
        "model",
        "capability_overall",
        "rougeL_fmeasure",
        "meteor_lite",
        "quality_factuality",
        "compression_ratio",
        "latency_seconds",
    ]
    cols = [c for c in cols if c in detailed.columns]
    if len(cols) < 5:
        return
    sample = sample_df(detailed[cols].dropna(), min(sample_size, 9000), seed=123)
    grid = sns.pairplot(sample, hue="model", vars=[c for c in cols if c != "model"], palette=MODEL_PALETTE, corner=True, plot_kws={"alpha": 0.25, "s": 12, "linewidth": 0})
    grid.fig.suptitle(f"{run.name}: cekirdek metrik pairplot", fontsize=16, weight="bold", y=1.02)
    out_path = out_dir / run.name / "04_tradeoffs_scatter" / "core_metric_pairplot.png"
    ensure_dir(out_path.parent)
    grid.fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(grid.fig)
    manifest.add(run.name, "tradeoffs_scatter", out_path, "Core metric pairplot", "Cekirdek metrikler icin sample bazli ikili iliski matrisi.")


def pairwise_winner_tables(detailed: pd.DataFrame, metrics: list[str]) -> dict[str, pd.DataFrame]:
    result: dict[str, pd.DataFrame] = {}
    id_cols = ["language", "sample_id"]
    for metric in metrics:
        if metric not in detailed.columns:
            continue
        pivot = detailed.pivot_table(index=id_cols, columns="model", values=metric, aggfunc="mean", observed=True).dropna()
        if pivot.empty:
            continue
        higher = HIGHER_IS_BETTER.get(metric, True)
        winners = pivot.idxmax(axis=1) if higher else pivot.idxmin(axis=1)
        table = winners.rename("winner").reset_index()
        table["metric"] = metric
        result[metric] = table
    return result


def plot_pairwise_wins(run: EvalRun, detailed: pd.DataFrame, out_dir: Path, manifest: Manifest) -> None:
    tables = pairwise_winner_tables(detailed, PAIRWISE_METRICS)
    all_rows = []
    for metric, table in tables.items():
        counts = table.groupby(["language", "winner"], observed=True).size().rename("wins").reset_index()
        total = table.groupby("language", observed=True).size().rename("total").reset_index()
        counts = counts.merge(total, on="language")
        counts["win_rate"] = counts["wins"] / counts["total"]
        counts["metric"] = metric
        all_rows.append(counts)

        pivot = counts.pivot(index="language", columns="winner", values="win_rate").fillna(0)
        fig, ax = plt.subplots(figsize=(7.2, 7.2))
        sns.heatmap(pivot, annot=True, fmt=".2f", cmap="crest", linewidths=0.5, vmin=0, vmax=1, ax=ax)
        ax.set_title(f"{run.name}: sample kazanma orani - {metric_label(metric)}", fontsize=14, weight="bold")
        ax.set_xlabel("Kazanan model")
        ax.set_ylabel("Dil")
        save_figure(
            fig,
            out_dir / run.name / "05_sample_pairwise" / "win_rate_heatmaps" / f"win_rate_{clean_name(metric)}.png",
            manifest,
            run.name,
            "sample_pairwise",
            f"{metric_label(metric)} win-rate heatmap",
            "Ayni sample icin modeller arasinda hangi modelin kazandigini dil bazinda gosterir.",
        )

    if all_rows:
        summary = pd.concat(all_rows, ignore_index=True)
        overall = summary.groupby(["metric", "winner"], observed=True).agg({"wins": "sum", "total": "sum"}).reset_index()
        overall["win_rate"] = overall["wins"] / overall["total"]
        pivot = overall.pivot(index="metric", columns="winner", values="win_rate").fillna(0)
        fig, ax = plt.subplots(figsize=(8, max(5.5, len(pivot) * 0.5)))
        sns.heatmap(pivot, annot=True, fmt=".2f", cmap="crest", linewidths=0.5, vmin=0, vmax=1, ax=ax)
        ax.set_title(f"{run.name}: metrik bazli genel sample kazanma oranlari", fontsize=14, weight="bold")
        ax.set_xlabel("Model")
        ax.set_ylabel("Metrik")
        ax.set_yticklabels([metric_label(m) for m in pivot.index])
        save_figure(
            fig,
            out_dir / run.name / "05_sample_pairwise" / "overall_win_rate_by_metric.png",
            manifest,
            run.name,
            "sample_pairwise",
            "Overall sample win rates by metric",
            "Tum dillerde sample bazli kazanma oranlarini metrik bazinda ozetler.",
        )


def plot_pairwise_deltas(run: EvalRun, detailed: pd.DataFrame, out_dir: Path, manifest: Manifest, sample_size: int) -> None:
    model_pairs = [("mt5-xlsum", "mbart50_xlsum"), ("mt5-xlsum", "mbart-xlsum-2"), ("mbart50_xlsum", "mbart-xlsum-2")]
    rows = []
    for metric in PAIRWISE_METRICS:
        if metric not in detailed.columns:
            continue
        pivot = detailed.pivot_table(index=["language", "sample_id"], columns="model", values=metric, aggfunc="mean", observed=True).dropna()
        for left, right in model_pairs:
            if left in pivot.columns and right in pivot.columns:
                delta = pivot[left] - pivot[right]
                temp = delta.rename("delta").reset_index()
                temp["metric"] = metric
                temp["pair"] = f"{left} - {right}"
                rows.append(temp)
    if not rows:
        return
    delta_df = pd.concat(rows, ignore_index=True)
    plot_df = sample_df(delta_df, sample_size)
    fig, ax = plt.subplots(figsize=(14, max(6, len(PAIRWISE_METRICS) * 0.75)))
    sns.boxplot(data=plot_df, y="metric", x="delta", hue="pair", fliersize=0.5, linewidth=0.8, ax=ax)
    ax.axvline(0, color="black", linewidth=1)
    ax.set_title(f"{run.name}: sample bazli model fark dagilimlari", fontsize=14, weight="bold")
    ax.set_xlabel("Sol model - sag model")
    ax.set_ylabel("Metrik")
    ax.set_yticklabels([metric_label(t.get_text()) for t in ax.get_yticklabels()])
    ax.legend(title="Model cifti", fontsize=8)
    ax.grid(axis="x", alpha=0.25)
    save_figure(
        fig,
        out_dir / run.name / "05_sample_pairwise" / "pairwise_delta_boxplots.png",
        manifest,
        run.name,
        "sample_pairwise",
        "Pairwise delta boxplots",
        "Ayni sample uzerinden iki model arasindaki skor farklarinin dagilimi.",
    )


def plot_interactive_language(run: EvalRun, language: pd.DataFrame, out_dir: Path, manifest: Manifest) -> None:
    if px is None:
        return
    metrics = [m for m in ["capability_overall_mean", "rougeL_fmeasure_mean", "bleu_mean", "meteor_lite_mean", "quality_factuality_mean", "latency_seconds_mean"] if m in language.columns]
    if not metrics:
        return
    fig = px.parallel_coordinates(
        language,
        dimensions=metrics,
        color="capability_overall_mean" if "capability_overall_mean" in language.columns else metrics[0],
        labels={m: metric_label(m) for m in metrics},
        title=f"{run.name}: model-language parallel coordinates",
    )
    write_html(
        out_dir / run.name / "06_interactive" / "language_parallel_coordinates.html",
        fig.to_html(include_plotlyjs="cdn"),
        manifest,
        run.name,
        "interactive",
        "Language parallel coordinates",
        "Dil-model satirlarini interaktif paralel koordinat grafigiyle gosterir.",
    )

    fig = px.scatter(
        language,
        x="rougeL_fmeasure_mean",
        y="capability_overall_mean",
        color="model",
        size="samples" if "samples" in language.columns else None,
        symbol="language",
        hover_data=["language", "model", "bleu_mean", "meteor_lite_mean"],
        title=f"{run.name}: ROUGE-L vs capability overall",
        color_discrete_map=MODEL_PALETTE,
    )
    write_html(
        out_dir / run.name / "06_interactive" / "language_rougel_vs_capability_scatter.html",
        fig.to_html(include_plotlyjs="cdn"),
        manifest,
        run.name,
        "interactive",
        "Interactive ROUGE-L vs capability scatter",
        "Dil-model satirlarini ornek sayisina gore olceklenmis interaktif scatter olarak gosterir.",
    )


def plot_cross_run(runs: list[EvalRun], out_dir: Path, manifest: Manifest) -> None:
    if len(runs) < 2:
        return
    language_frames = []
    overall_frames = []
    for run in runs:
        lang = read_language(run)
        lang["run"] = run.name
        language_frames.append(lang)
        overall = read_overall(run)
        overall["run"] = run.name
        overall_frames.append(overall)
    language = pd.concat(language_frames, ignore_index=True)
    overall = pd.concat(overall_frames, ignore_index=True)
    run_names = sorted(language["run"].unique())
    if len(run_names) < 2:
        return

    metric = "capability_overall_mean"
    if metric in language.columns:
        pivot = language.pivot_table(index=["language", "model"], columns="run", values=metric, observed=True).dropna()
        if len(run_names) >= 2:
            left, right = run_names[0], run_names[-1]
            fig, ax = plt.subplots(figsize=(7, 7))
            plot_df = pivot.reset_index()
            sns.scatterplot(data=plot_df, x=left, y=right, hue="model", style="language", palette=MODEL_PALETTE, s=90, ax=ax)
            lo = min(plot_df[left].min(), plot_df[right].min())
            hi = max(plot_df[left].max(), plot_df[right].max())
            ax.plot([lo, hi], [lo, hi], color="black", linestyle="--", linewidth=1)
            ax.set_title(f"Run stabilitesi: {right} vs {left}", fontsize=14, weight="bold")
            ax.set_xlabel(f"{left} {metric_label(metric)}")
            ax.set_ylabel(f"{right} {metric_label(metric)}")
            ax.grid(alpha=0.25)
            save_figure(
                fig,
                out_dir / "cross_run" / "full_vs_200_capability_scatter.png",
                manifest,
                "cross_run",
                "cross_run",
                "Full vs 200 capability scatter",
                "Dil-model seviyesinde iki run arasindaki capability skor stabilitesi.",
            )

            diff = (pivot[right] - pivot[left]).rename("delta").reset_index()
            mat = diff.pivot(index="language", columns="model", values="delta")
            fig, ax = plt.subplots(figsize=(7.2, 7.2))
            lim = np.nanmax(np.abs(mat.to_numpy()))
            sns.heatmap(mat, annot=True, fmt=".3f", cmap="vlag", center=0, vmin=-lim, vmax=lim, linewidths=0.5, ax=ax)
            ax.set_title(f"Run farki: {right} - {left}", fontsize=14, weight="bold")
            ax.set_xlabel("Model")
            ax.set_ylabel("Dil")
            save_figure(
                fig,
                out_dir / "cross_run" / "full_vs_200_capability_delta_heatmap.png",
                manifest,
                "cross_run",
                "cross_run",
                "Full vs 200 capability delta heatmap",
                "Dil-model seviyesinde full ve 200 run capability farklari.",
            )

    metrics = [m for group in OVERALL_GROUPS.values() for m in group if m in overall.columns]
    rows = []
    for metric in metrics:
        pivot = overall.pivot(index="model", columns="run", values=metric)
        if len(run_names) >= 2:
            left, right = run_names[0], run_names[-1]
            if left in pivot.columns and right in pivot.columns:
                for model, delta in (pivot[right] - pivot[left]).items():
                    rows.append({"model": model, "metric": metric, "delta": delta})
    if rows:
        delta_df = pd.DataFrame(rows)
        mat = delta_df.pivot(index="metric", columns="model", values="delta")
        fig, ax = plt.subplots(figsize=(8, max(8, len(mat) * 0.33)))
        lim = np.nanmax(np.abs(mat.to_numpy()))
        sns.heatmap(mat, annot=True, fmt=".3f", cmap="vlag", center=0, vmin=-lim, vmax=lim, linewidths=0.4, ax=ax)
        ax.set_title("Overall run farklari", fontsize=14, weight="bold")
        ax.set_xlabel("Model")
        ax.set_ylabel("Metrik")
        ax.set_yticklabels([metric_label(m) for m in mat.index])
        save_figure(
            fig,
            out_dir / "cross_run" / "overall_metric_delta_heatmap.png",
            manifest,
            "cross_run",
            "cross_run",
            "Overall metric delta heatmap",
            "Overall macro summary seviyesinde run'lar arasi metrik farklari.",
        )


def generate_for_run(run: EvalRun, out_dir: Path, manifest: Manifest, sample_size: int) -> None:
    print(f"[run] {run.name}", flush=True)
    overall = read_overall(run)
    language = read_language(run)

    plot_overall_grouped_bars(run, overall, out_dir, manifest)
    plot_overall_heatmaps(run, overall, out_dir, manifest)
    plot_radar(run, overall, OVERALL_GROUPS["capability"], "radar_capability_metrics.png", "Capability radar", out_dir, manifest)
    plot_radar(run, overall, OVERALL_GROUPS["classical"], "radar_classical_metrics.png", "Klasik metrik radar", out_dir, manifest)
    plot_overall_tradeoffs(run, overall, out_dir, manifest)

    plot_language_heatmaps(run, language, out_dir, manifest)
    plot_language_deltas(run, language, out_dir, manifest)
    plot_language_rank_and_winners(run, language, out_dir, manifest)
    plot_language_metric_small_multiples(run, language, out_dir, manifest)
    plot_samples_by_language(run, language, out_dir, manifest)
    plot_interactive_language(run, language, out_dir, manifest)

    detailed = read_detailed(run)
    plot_detailed_distributions(run, detailed, out_dir, manifest, sample_size)
    plot_detailed_correlations(run, detailed, out_dir, manifest, sample_size)
    plot_detailed_scatter(run, detailed, out_dir, manifest, sample_size)
    plot_pairplot(run, detailed, out_dir, manifest, sample_size)
    plot_pairwise_wins(run, detailed, out_dir, manifest)
    plot_pairwise_deltas(run, detailed, out_dir, manifest, sample_size)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=Path("evaluation"), help="Evaluation root directory.")
    parser.add_argument("--output-dir", type=Path, default=Path("evaluation/eval_visualizations"), help="Output directory for generated visuals.")
    parser.add_argument("--sample-size", type=int, default=60000, help="Maximum rows sampled for heavy detailed plots.")
    parser.add_argument("--run-names", nargs="*", default=None, help="Optional run directory names to include, e.g. xlsum_eval_full.")
    parser.add_argument("--clean-output", action="store_true", help="Delete the output directory before regenerating visuals.")
    args = parser.parse_args()

    sns.set_theme(style="whitegrid", context="notebook")
    if args.clean_output and args.output_dir.exists():
        shutil.rmtree(args.output_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    runs = discover_runs(args.input_root)
    if args.run_names:
        requested = set(args.run_names)
        runs = [run for run in runs if run.name in requested]
    if not runs:
        raise SystemExit(f"No evaluation runs found under {args.input_root}")

    manifest = Manifest()
    for run in runs:
        generate_for_run(run, args.output_dir, manifest, args.sample_size)

    plot_cross_run(runs, args.output_dir, manifest)
    manifest.write(args.output_dir)
    print(f"[done] {len(manifest.rows)} visualization files indexed at {args.output_dir}", flush=True)


if __name__ == "__main__":
    main()
