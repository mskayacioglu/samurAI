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
    "mt5-xlsum": "mT5 XL-Sum (prêt)",
    "mbart50_xlsum": "mBART50 (entraîné)",
    "mbart-xlsum-2": "mBART-2 (entraîné)",
}
MODEL_PALETTE = {
    "mt5-xlsum": "#3b6fb6",
    "mbart50_xlsum": "#d95f02",
    "mbart-xlsum-2": "#1b9e77",
}

LANGUAGE_NAMES = {
    "ar": "Arabe",
    "en": "Anglais",
    "es": "Espagnol",
    "fr": "Français",
    "hi": "Hindi",
    "ja": "Japonais",
    "ko": "Coréen",
    "ru": "Russe",
    "tr": "Turc",
    "vi": "Vietnamien",
    "zh": "Chinois",
}

GROUP_LABELS = {
    "classical": "métriques classiques",
    "capability": "capacité",
    "quality": "qualité",
    "quality_grounding": "qualité et ancrage à la source",
    "behavior_efficiency": "comportement et efficacité",
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
    ("source_tokens", "latency_seconds", "Longueur de la source et temps de génération"),
    ("source_tokens", "summary_tokens", "Longueur de la source et du résumé"),
    ("compression_ratio", "capability_overall", "Compression et capacité globale"),
    ("compression_ratio", "rougeL_fmeasure", "Compression et ROUGE-L"),
    ("latency_per_1k_tokens", "capability_efficiency", "Latence normalisée et efficacité"),
    ("source_coverage", "quality_factuality", "Couverture de la source et proxy de factualité"),
    ("source_recall", "capability_relevance", "Rappel de la source et proxy de pertinence"),
    ("rougeL_fmeasure", "capability_accuracy", "ROUGE-L et proxy d'exactitude"),
    ("repetition_3gram", "capability_clarity", "Répétition et proxy de clarté"),
    ("novelty_2gram", "rougeL_fmeasure", "Nouveauté et ROUGE-L"),
    ("fragment_density", "novelty_2gram", "Extractivité et nouveauté"),
    ("summary_tokens", "quality_completeness", "Longueur du résumé et proxy de complétude"),
]

INTERACTIVE_SCREENSHOTS = [
    (
        "parallel_cordinates.png",
        "Capture d'écran interactive des coordonnées parallèles",
        "Capture d'écran des coordonnées parallèles interactives affichant les lignes langue-modèle sur les axes métriques.",
    ),
    (
        "rougel-vs-cap.png",
        "Capture d'écran interactive ROUGE-L et capacité globale",
        "Capture d'écran du nuage de points interactif affichant les lignes langue-modèle selon ROUGE-L et la capacité globale.",
    ),
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
    exact = {
        "rouge1": "ROUGE-1",
        "rouge2": "ROUGE-2",
        "rougeL": "ROUGE-L",
        "bleu": "BLEU",
        "meteor_lite": "METEOR-lite",
        "capability_overall": "Capacité globale",
        "capability_coherence": "Cohérence",
        "capability_accuracy": "Exactitude",
        "capability_clarity": "Clarté",
        "capability_relevance": "Pertinence",
        "capability_efficiency": "Efficacité",
        "quality_factuality": "Factualité",
        "quality_completeness": "Complétude",
        "source_coverage": "Couverture de la source",
        "source_recall": "Rappel de la source",
        "fragment_coverage": "Couverture des fragments",
        "fragment_density": "Densité des fragments",
        "latency_seconds": "Latence (secondes)",
        "latency_per_1k_tokens": "Latence par 1k tokens",
        "compression_ratio": "Taux de compression",
        "novelty_1gram": "Nouveauté 1-gramme",
        "novelty_2gram": "Nouveauté 2-grammes",
        "repetition_3gram": "Répétition 3-grammes",
        "summary_tokens": "Tokens du résumé",
        "source_tokens": "Tokens de la source",
    }
    label = metric
    for suffix in ("_mean", "_std", "_fmeasure"):
        label = label.replace(suffix, "")
    if label in exact:
        return exact[label]
    return label.replace("_", " ").capitalize()


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


def zero_based_upper(values: pd.Series | np.ndarray, metric: str | None = None) -> float:
    series = pd.Series(values).replace([np.inf, -np.inf], np.nan).dropna()
    if series.empty:
        return 1.0
    vmax = float(series.max())
    if vmax <= 1.0 and (metric is None or "tokens" not in metric):
        return 1.0
    return vmax * 1.08 if vmax > 0 else 1.0


def set_zero_based_axes(ax: plt.Axes, x_values: pd.Series | np.ndarray, y_values: pd.Series | np.ndarray, x_metric: str | None = None, y_metric: str | None = None) -> None:
    ax.set_xlim(left=0, right=zero_based_upper(x_values, x_metric))
    ax.set_ylim(bottom=0, top=zero_based_upper(y_values, y_metric))


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
        group_label = GROUP_LABELS.get(group_name, group_name)
        ax.set_title(f"{run.name}: comparaison des modèles - {group_label}", fontsize=14, weight="bold")
        ax.set_xlabel("")
        ax.set_ylabel("Valeur moyenne")
        ax.tick_params(axis="x", rotation=35)
        ax.legend(title="Modèle", loc="best")
        ax.grid(axis="y", alpha=0.25)
        save_figure(
            fig,
            out_dir / run.name / "01_overall" / f"overall_grouped_bar_{group_name}.png",
            manifest,
            run.name,
            "overall",
            f"Barres groupées - {group_label}",
            "Diagramme en barres groupées des métriques par modèle à partir du résumé macro global.",
        )


def plot_overall_heatmaps(run: EvalRun, overall: pd.DataFrame, out_dir: Path, manifest: Manifest) -> None:
    metrics = [m for group in OVERALL_GROUPS.values() for m in group if m in overall.columns]
    data = overall.set_index("model")[metrics].T
    fig, ax = plt.subplots(figsize=(8, max(8, len(metrics) * 0.33)))
    sns.heatmap(data, annot=True, fmt=".3f", cmap="viridis", linewidths=0.4, ax=ax)
    ax.set_title(f"{run.name}: matrice globale des métriques", fontsize=14, weight="bold")
    ax.set_xlabel("Modèle")
    ax.set_ylabel("Métrique")
    ax.set_yticklabels([metric_label(m) for m in metrics])
    save_figure(
        fig,
        out_dir / run.name / "01_overall" / "overall_metric_heatmap.png",
        manifest,
        run.name,
        "overall",
        "Carte thermique des métriques globales",
        "Vue en carte thermique de toutes les métriques macro par modèle.",
    )

    rank_df = data.copy()
    for metric in rank_df.index:
        ascending = not HIGHER_IS_BETTER.get(metric, True)
        rank_df.loc[metric] = rank_df.loc[metric].rank(ascending=ascending, method="min")
    fig, ax = plt.subplots(figsize=(7, max(8, len(metrics) * 0.33)))
    sns.heatmap(rank_df, annot=True, fmt=".0f", cmap="YlGnBu_r", linewidths=0.4, cbar_kws={"label": "Rang (1 = meilleur)"}, ax=ax)
    ax.set_title(f"{run.name}: classement des modèles par métrique", fontsize=14, weight="bold")
    ax.set_xlabel("Modèle")
    ax.set_ylabel("Métrique")
    ax.set_yticklabels([metric_label(m) for m in metrics])
    save_figure(
        fig,
        out_dir / run.name / "01_overall" / "overall_rank_heatmap.png",
        manifest,
        run.name,
        "overall",
        "Carte thermique des rangs globaux",
        "Affiche le classement des modèles pour chaque métrique; 1 correspond au meilleur score.",
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
        "Compare les profils des modèles dans un graphique radar.",
    )


def plot_overall_tradeoffs(run: EvalRun, overall: pd.DataFrame, out_dir: Path, manifest: Manifest) -> None:
    pairs = [
        ("latency_seconds_mean", "capability_overall_mean", "Latence vs capacité globale"),
        ("compression_ratio_mean", "quality_completeness_mean", "Compression vs complétude"),
        ("source_coverage_mean", "quality_factuality_mean", "Couverture de la source vs factualité"),
        ("capability_efficiency_mean", "rougeL_fmeasure_mean", "Efficacité vs ROUGE-L"),
    ]
    for x, y, title in pairs:
        if x not in overall.columns or y not in overall.columns:
            continue
        fig, ax = plt.subplots(figsize=(8, 6))
        for idx, (_, row) in enumerate(overall.iterrows()):
            model = str(row["model"])
            ax.scatter(row[x], row[y], s=220, color=MODEL_PALETTE.get(model), edgecolor="white", linewidth=1.2)
            offset = [(8, 8), (8, -14), (-74, 8)][idx % 3]
            ax.annotate(model, (row[x], row[y]), xytext=offset, textcoords="offset points", fontsize=9)
        ax.set_title(f"{run.name}: {title}", fontsize=14, weight="bold")
        ax.set_xlabel(metric_label(x))
        ax.set_ylabel(metric_label(y))
        set_zero_based_axes(ax, overall[x], overall[y], x, y)
        ax.grid(alpha=0.25)
        save_figure(
            fig,
            out_dir / run.name / "01_overall" / f"overall_tradeoff_{clean_name(x)}__{clean_name(y)}.png",
            manifest,
            run.name,
            "overall",
            title,
            "Affiche le compromis entre deux métriques au niveau macro.",
        )


def plot_language_heatmaps(run: EvalRun, language: pd.DataFrame, out_dir: Path, manifest: Manifest) -> None:
    for metric in [m for m in LANGUAGE_HEATMAP_METRICS if m in language.columns]:
        pivot = language.pivot(index="language", columns="model", values=metric)
        fig, ax = plt.subplots(figsize=(7.2, 7.2))
        cmap = "mako_r" if not HIGHER_IS_BETTER.get(metric, True) else "viridis"
        sns.heatmap(pivot, annot=True, fmt=".3f", cmap=cmap, linewidths=0.5, ax=ax)
        ax.set_title(f"{run.name}: {metric_label(metric)} par langue et modèle", fontsize=14, weight="bold")
        ax.set_xlabel("Modèle")
        ax.set_ylabel("Langue")
        ax.set_yticklabels([LANGUAGE_NAMES.get(str(t.get_text()), str(t.get_text())) for t in ax.get_yticklabels()], rotation=0)
        save_figure(
            fig,
            out_dir / run.name / "02_language_summary" / "metric_heatmaps" / f"language_model_heatmap_{clean_name(metric)}.png",
            manifest,
            run.name,
            "language_summary",
            f"Carte thermique - {metric_label(metric)}",
            "Moyennes de la métrique dans la matrice langue x modèle.",
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
        ax.set_title(f"{run.name}: écarts langue-métrique {left} moins {right}", fontsize=14, weight="bold")
        ax.set_xlabel("Langue")
        ax.set_ylabel("Métrique")
        ax.set_yticklabels([metric_label(m) for m in mat.index])
        save_figure(
            fig,
            out_dir / run.name / "02_language_summary" / "pairwise_deltas" / f"language_metric_delta_{clean_name(left)}_minus_{clean_name(right)}.png",
            manifest,
            run.name,
            "language_summary",
            f"Écarts de métriques {left} - {right}",
            "Écarts moyens de score entre deux modèles par langue et par métrique.",
        )


def plot_language_rank_and_winners(run: EvalRun, language: pd.DataFrame, out_dir: Path, manifest: Manifest) -> None:
    metric = "capability_overall_mean"
    if metric not in language.columns:
        return
    pivot = language.pivot(index="language", columns="model", values=metric)
    rank = pivot.rank(axis=1, ascending=False, method="min")
    fig, ax = plt.subplots(figsize=(7.2, 7.2))
    sns.heatmap(rank, annot=True, fmt=".0f", cmap="YlGnBu_r", linewidths=0.5, cbar_kws={"label": "Rang (1 = meilleur)"}, ax=ax)
    ax.set_title(f"{run.name}: classement de la capacité par langue", fontsize=14, weight="bold")
    ax.set_xlabel("Modèle")
    ax.set_ylabel("Langue")
    save_figure(
        fig,
        out_dir / run.name / "02_language_summary" / "language_capability_rank_heatmap.png",
        manifest,
        run.name,
        "language_summary",
        "Carte thermique du rang de capacité par langue",
        "Classement des modèles pour la capacité globale moyenne dans chaque langue.",
    )

    winners = pivot.idxmax(axis=1).rename("winner").reset_index()
    winners["language_label"] = winners["language"].astype(str).map(lambda x: LANGUAGE_NAMES.get(x, x))
    fig, ax = plt.subplots(figsize=(10, 5.5))
    sns.countplot(data=winners, x="winner", order=model_order(winners["winner"]), palette=MODEL_PALETTE, ax=ax)
    add_value_labels(ax, fmt="{:.0f}")
    ax.set_title(f"{run.name}: nombre de victoires par langue", fontsize=14, weight="bold")
    ax.set_xlabel("Modèle gagnant")
    ax.set_ylabel("Nombre de langues")
    ax.grid(axis="y", alpha=0.25)
    save_figure(
        fig,
        out_dir / run.name / "02_language_summary" / "language_winner_counts.png",
        manifest,
        run.name,
        "language_summary",
        "Nombre de victoires par langue",
        "Nombre de langues où chaque modèle est premier selon la capacité globale.",
    )

    sorted_langs = pivot.mean(axis=1).sort_values(ascending=False).index
    plot_df = language[language["language"].isin(sorted_langs)].copy()
    plot_df["language"] = pd.Categorical(plot_df["language"], categories=list(sorted_langs), ordered=True)
    fig, ax = plt.subplots(figsize=(12, 6))
    sns.lineplot(data=plot_df.sort_values("language"), x="language", y=metric, hue="model", marker="o", palette=MODEL_PALETTE, ax=ax)
    ax.set_title(f"{run.name}: profil de capacité selon les langues", fontsize=14, weight="bold")
    ax.set_xlabel("Langue")
    ax.set_ylabel("Capacité globale moyenne")
    ax.grid(axis="y", alpha=0.25)
    save_figure(
        fig,
        out_dir / run.name / "02_language_summary" / "language_capability_profile_lines.png",
        manifest,
        run.name,
        "language_summary",
        "Lignes de profil de capacité par langue",
        "Affiche le profil de capacité globale des modèles selon les langues.",
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
        fig.legend(handles, labels, loc="upper center", ncol=3, title="Modèle")
        group_label = GROUP_LABELS.get(group, group)
        fig.suptitle(f"{run.name}: profils des métriques {group_label} par langue", fontsize=16, weight="bold", y=1.01)
        fig.tight_layout()
        save_figure(
            fig,
            out_dir / run.name / "02_language_summary" / f"language_small_multiples_{group}.png",
            manifest,
            run.name,
            "language_summary",
            f"Petits multiples par langue - {group_label}",
            "Affiche les profils des modèles par langue avec de petits multiples pour le même groupe de métriques.",
        )


def plot_samples_by_language(run: EvalRun, language: pd.DataFrame, out_dir: Path, manifest: Manifest) -> None:
    if "samples" not in language.columns:
        return
    sample_df = language.drop_duplicates("language")[["language", "samples"]].sort_values("samples", ascending=False)
    fig, ax = plt.subplots(figsize=(10, 5.5))
    sns.barplot(data=sample_df, x="language", y="samples", color="#4c78a8", ax=ax)
    add_value_labels(ax, fmt="{:.0f}", rotation=90)
    ax.set_title(f"{run.name}: nombre d'échantillons par langue", fontsize=14, weight="bold")
    ax.set_xlabel("Langue")
    ax.set_ylabel("Nombre d'échantillons")
    ax.grid(axis="y", alpha=0.25)
    save_figure(
        fig,
        out_dir / run.name / "02_language_summary" / "language_sample_counts.png",
        manifest,
        run.name,
        "language_summary",
        "Nombre d'échantillons par langue",
        "Nombre d'échantillons d'évaluation pour chaque langue.",
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
        fig, ax = plt.subplots(figsize=(8.5, 5.8))
        sns.violinplot(data=sample, x="model", y=metric, order=model_order(sample["model"].astype(str)), palette=MODEL_PALETTE, inner="quartile", cut=0, ax=ax)
        ax.set_title(f"{run.name}: distribution de {metric_label(metric)} par modèle", fontsize=14, weight="bold")
        ax.set_xlabel("Modèle")
        ax.set_ylabel(metric_label(metric))
        ax.tick_params(axis="x", rotation=15)
        ax.grid(axis="y", alpha=0.25)
        fig.tight_layout()
        save_figure(
            fig,
            out_dir / run.name / "03_detailed_distributions" / f"distribution_model_{clean_name(metric)}.png",
            manifest,
            run.name,
            "detailed_distributions",
            f"Distribution de {metric_label(metric)} par modèle",
            "Affiche la distribution par modèle au niveau des métriques détaillées.",
        )

        fig, ax = plt.subplots(figsize=(13, 6.6))
        sns.boxplot(data=sample, x="language", y=metric, hue="model", palette=MODEL_PALETTE, fliersize=0.45, linewidth=0.8, ax=ax)
        ax.set_title(f"{run.name}: distribution de {metric_label(metric)} par langue et modèle", fontsize=14, weight="bold")
        ax.set_xlabel("Langue")
        ax.set_ylabel(metric_label(metric))
        ax.tick_params(axis="x", rotation=0)
        ax.legend(title="Modèle", fontsize=8, loc="best")
        ax.grid(axis="y", alpha=0.25)
        fig.tight_layout()
        save_figure(
            fig,
            out_dir / run.name / "03_detailed_distributions" / f"distribution_language_model_{clean_name(metric)}.png",
            manifest,
            run.name,
            "detailed_distributions",
            f"Distribution langue-modèle de {metric_label(metric)}",
            "Affiche la distribution par langue et par modèle au niveau des métriques détaillées.",
        )

        fig, ax = plt.subplots(figsize=(10, 5.5))
        sns.ecdfplot(data=sample, x=metric, hue="model", hue_order=model_order(sample["model"].astype(str)), palette=MODEL_PALETTE, ax=ax)
        ax.set_title(f"{run.name}: {metric_label(metric)} ECDF", fontsize=14, weight="bold")
        ax.set_xlabel(metric_label(metric))
        ax.set_ylabel("Proportion cumulative")
        ax.grid(alpha=0.25)
        save_figure(
            fig,
            out_dir / run.name / "03_detailed_distributions" / f"ecdf_{clean_name(metric)}.png",
            manifest,
            run.name,
            "detailed_distributions",
            f"{metric_label(metric)} ECDF",
            "Compare les distributions des modèles de manière cumulative.",
        )

    long = sample.melt(id_vars=["model", "language"], value_vars=metrics, var_name="metric", value_name="value").dropna()
    stats = long.groupby(["metric", "model"], observed=True)["value"].agg(["mean", "median", "std"]).reset_index()
    for stat in ["mean", "median", "std"]:
        pivot = stats.pivot(index="metric", columns="model", values=stat)
        fig, ax = plt.subplots(figsize=(8, max(8, len(metrics) * 0.27)))
        sns.heatmap(pivot, annot=True, fmt=".3f", cmap="viridis", linewidths=0.3, ax=ax)
        stat_label = {"mean": "moyenne", "median": "médiane", "std": "écart-type"}[stat]
        ax.set_title(f"{run.name}: résumé détaillé - {stat_label}", fontsize=14, weight="bold")
        ax.set_xlabel("Modèle")
        ax.set_ylabel("Métrique")
        ax.set_yticklabels([metric_label(m) for m in pivot.index])
        save_figure(
            fig,
            out_dir / run.name / "03_detailed_distributions" / f"detailed_metric_{stat}_heatmap.png",
            manifest,
            run.name,
            "detailed_distributions",
            f"Carte thermique des métriques détaillées - {stat_label}",
            "Matrice statistique résumée par modèle à partir des métriques détaillées.",
        )


def plot_detailed_correlations(run: EvalRun, detailed: pd.DataFrame, out_dir: Path, manifest: Manifest, sample_size: int) -> None:
    sample = sample_df(detailed, sample_size)
    metrics = [m for m in DETAILED_KEY_METRICS if m in sample.columns]
    corr = sample[metrics].corr(numeric_only=True)
    fig, ax = plt.subplots(figsize=(14, 12))
    sns.heatmap(corr, cmap="vlag", center=0, linewidths=0.25, ax=ax)
    ax.set_title(f"{run.name}: matrice de corrélation des métriques", fontsize=15, weight="bold")
    ax.set_xticklabels([metric_label(t.get_text()) for t in ax.get_xticklabels()], rotation=45, ha="right")
    ax.set_yticklabels([metric_label(t.get_text()) for t in ax.get_yticklabels()], rotation=0)
    save_figure(
        fig,
        out_dir / run.name / "03_detailed_distributions" / "correlation_all_metrics.png",
        manifest,
        run.name,
        "detailed_distributions",
        "Carte thermique de corrélation de toutes les métriques",
        "Carte des corrélations entre les métriques numériques au niveau détaillé.",
    )

    for model in model_order(sample["model"].astype(str)):
        model_df = sample[sample["model"].astype(str) == model]
        if len(model_df) < 10:
            continue
        corr = model_df[metrics].corr(numeric_only=True)
        fig, ax = plt.subplots(figsize=(14, 12))
        sns.heatmap(corr, cmap="vlag", center=0, linewidths=0.25, ax=ax)
        ax.set_title(f"{run.name}: corrélations des métriques - {model}", fontsize=15, weight="bold")
        ax.set_xticklabels([metric_label(t.get_text()) for t in ax.get_xticklabels()], rotation=45, ha="right")
        ax.set_yticklabels([metric_label(t.get_text()) for t in ax.get_yticklabels()], rotation=0)
        save_figure(
            fig,
            out_dir / run.name / "03_detailed_distributions" / "correlations_by_model" / f"correlation_{clean_name(model)}.png",
            manifest,
            run.name,
            "detailed_distributions",
            f"Carte thermique de corrélation - {model}",
            "Corrélations des métriques détaillées pour un seul modèle.",
        )


def plot_detailed_scatter(run: EvalRun, detailed: pd.DataFrame, out_dir: Path, manifest: Manifest, sample_size: int) -> None:
    sample = sample_df(detailed, sample_size)
    for x, y, title in SCATTER_PAIRS:
        if x not in sample.columns or y not in sample.columns:
            continue
        fig, axes = plt.subplots(2, 1, figsize=(9.5, 12.5))
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
        axes[0].set_title("Nuage de points coloré par modèle", weight="bold")
        axes[0].set_xlabel(metric_label(x))
        axes[0].set_ylabel(metric_label(y))
        set_zero_based_axes(axes[0], sample[x], sample[y], x, y)
        axes[0].grid(alpha=0.2)
        axes[0].legend(title="Modèle", fontsize=8)

        hb = axes[1].hexbin(sample[x], sample[y], gridsize=45, mincnt=1, cmap="magma", bins="log")
        axes[1].set_title("Hexbin de densité", weight="bold")
        axes[1].set_xlabel(metric_label(x))
        axes[1].set_ylabel(metric_label(y))
        set_zero_based_axes(axes[1], sample[x], sample[y], x, y)
        fig.colorbar(hb, ax=axes[1], label="log(count)")
        fig.suptitle(f"{run.name}: {title}", fontsize=15, weight="bold")
        fig.tight_layout(rect=(0, 0, 1, 0.97))
        save_figure(
            fig,
            out_dir / run.name / "04_tradeoffs_scatter" / f"scatter_hexbin_{clean_name(x)}__{clean_name(y)}.png",
            manifest,
            run.name,
            "tradeoffs_scatter",
            title,
            "Vue en nuage de points et densité au niveau des échantillons détaillés.",
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
    grid.fig.suptitle(f"{run.name}: matrice de relations des métriques centrales", fontsize=16, weight="bold", y=1.02)
    out_path = out_dir / run.name / "04_tradeoffs_scatter" / "core_metric_pairplot.png"
    ensure_dir(out_path.parent)
    grid.fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(grid.fig)
    manifest.add(run.name, "tradeoffs_scatter", out_path, "Matrice de relations des métriques centrales", "Matrice des relations deux à deux au niveau des échantillons pour les métriques centrales.")


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
        ax.set_title(f"{run.name}: taux de victoire par échantillon - {metric_label(metric)}", fontsize=14, weight="bold")
        ax.set_xlabel("Modèle gagnant")
        ax.set_ylabel("Langue")
        save_figure(
            fig,
            out_dir / run.name / "05_sample_pairwise" / "win_rate_heatmaps" / f"win_rate_{clean_name(metric)}.png",
            manifest,
            run.name,
            "sample_pairwise",
            f"Carte thermique du taux de victoire - {metric_label(metric)}",
            "Affiche par langue quel modèle gagne entre les modèles sur les mêmes échantillons.",
        )

    if all_rows:
        summary = pd.concat(all_rows, ignore_index=True)
        overall = summary.groupby(["metric", "winner"], observed=True).agg({"wins": "sum", "total": "sum"}).reset_index()
        overall["win_rate"] = overall["wins"] / overall["total"]
        pivot = overall.pivot(index="metric", columns="winner", values="win_rate").fillna(0)
        fig, ax = plt.subplots(figsize=(8, max(5.5, len(pivot) * 0.5)))
        sns.heatmap(pivot, annot=True, fmt=".2f", cmap="crest", linewidths=0.5, vmin=0, vmax=1, ax=ax)
        ax.set_title(f"{run.name}: taux de victoire globaux par métrique", fontsize=14, weight="bold")
        ax.set_xlabel("Modèle")
        ax.set_ylabel("Métrique")
        ax.set_yticklabels([metric_label(m) for m in pivot.index])
        save_figure(
            fig,
            out_dir / run.name / "05_sample_pairwise" / "overall_win_rate_by_metric.png",
            manifest,
            run.name,
            "sample_pairwise",
            "Taux de victoire globaux par métrique",
            "Résume les taux de victoire par échantillon et par métrique sur toutes les langues.",
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
    ax.set_title(f"{run.name}: distributions des écarts entre modèles par échantillon", fontsize=14, weight="bold")
    ax.set_xlabel("Modèle de gauche - modèle de droite")
    ax.set_ylabel("Métrique")
    ax.set_yticklabels([metric_label(t.get_text()) for t in ax.get_yticklabels()])
    ax.legend(title="Paire de modèles", fontsize=8)
    ax.grid(axis="x", alpha=0.25)
    save_figure(
        fig,
        out_dir / run.name / "05_sample_pairwise" / "pairwise_delta_boxplots.png",
        manifest,
        run.name,
        "sample_pairwise",
        "Boîtes à moustaches des écarts par paire",
        "Distribution des écarts de score entre deux modèles sur les mêmes échantillons.",
    )


def add_interactive_screenshots(run: EvalRun, out_dir: Path, manifest: Manifest, screenshot_dir: Path) -> None:
    target_dir = ensure_dir(out_dir / run.name / "06_interactive")
    for filename, title, description in INTERACTIVE_SCREENSHOTS:
        src = screenshot_dir / filename
        if not src.exists():
            continue
        dst = target_dir / filename
        if src.resolve() != dst.resolve():
            shutil.copy2(src, dst)
        manifest.add(run.name, "interactive", dst, title, description)


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
            ax.set_title(f"Stabilité des exécutions: {right} vs {left}", fontsize=14, weight="bold")
            ax.set_xlabel(f"{left} {metric_label(metric)}")
            ax.set_ylabel(f"{right} {metric_label(metric)}")
            ax.grid(alpha=0.25)
            save_figure(
                fig,
                out_dir / "cross_run" / "full_vs_200_capability_scatter.png",
                manifest,
                "cross_run",
                "cross_run",
                "Nuage de points de capacité full vs 200",
                "Stabilité des scores de capacité entre deux exécutions au niveau langue-modèle.",
            )

            diff = (pivot[right] - pivot[left]).rename("delta").reset_index()
            mat = diff.pivot(index="language", columns="model", values="delta")
            fig, ax = plt.subplots(figsize=(7.2, 7.2))
            lim = np.nanmax(np.abs(mat.to_numpy()))
            sns.heatmap(mat, annot=True, fmt=".3f", cmap="vlag", center=0, vmin=-lim, vmax=lim, linewidths=0.5, ax=ax)
            ax.set_title(f"Écart entre exécutions: {right} - {left}", fontsize=14, weight="bold")
            ax.set_xlabel("Modèle")
            ax.set_ylabel("Langue")
            save_figure(
                fig,
                out_dir / "cross_run" / "full_vs_200_capability_delta_heatmap.png",
                manifest,
                "cross_run",
                "cross_run",
                "Carte thermique des écarts de capacité full vs 200",
                "Écarts de capacité entre l'exécution complète et l'exécution 200 au niveau langue-modèle.",
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
        ax.set_title("Écarts globaux entre exécutions", fontsize=14, weight="bold")
        ax.set_xlabel("Modèle")
        ax.set_ylabel("Métrique")
        ax.set_yticklabels([metric_label(m) for m in mat.index])
        save_figure(
            fig,
            out_dir / "cross_run" / "overall_metric_delta_heatmap.png",
            manifest,
            "cross_run",
            "cross_run",
            "Carte thermique des écarts de métriques globaux",
            "Écarts de métriques entre exécutions au niveau du résumé macro global.",
        )


def generate_for_run(run: EvalRun, out_dir: Path, manifest: Manifest, sample_size: int, screenshot_dir: Path) -> None:
    print(f"[run] {run.name}", flush=True)
    overall = read_overall(run)
    language = read_language(run)

    plot_overall_grouped_bars(run, overall, out_dir, manifest)
    plot_overall_heatmaps(run, overall, out_dir, manifest)
    plot_radar(run, overall, OVERALL_GROUPS["capability"], "radar_capability_metrics.png", "Radar de capacité", out_dir, manifest)
    plot_radar(run, overall, OVERALL_GROUPS["classical"], "radar_classical_metrics.png", "Radar des métriques classiques", out_dir, manifest)
    plot_overall_tradeoffs(run, overall, out_dir, manifest)

    plot_language_heatmaps(run, language, out_dir, manifest)
    plot_language_deltas(run, language, out_dir, manifest)
    plot_language_rank_and_winners(run, language, out_dir, manifest)
    plot_language_metric_small_multiples(run, language, out_dir, manifest)
    plot_samples_by_language(run, language, out_dir, manifest)
    add_interactive_screenshots(run, out_dir, manifest, screenshot_dir)

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
    parser.add_argument("--interactive-screenshot-dir", type=Path, default=Path("evaluation/interactive_screenshots"), help="Directory containing PNG screenshots of interactive figures.")
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
        generate_for_run(run, args.output_dir, manifest, args.sample_size, args.interactive_screenshot_dir)

    plot_cross_run(runs, args.output_dir, manifest)
    manifest.write(args.output_dir)
    print(f"[done] {len(manifest.rows)} visualization files indexed at {args.output_dir}", flush=True)


if __name__ == "__main__":
    main()
