#!/usr/bin/env python3
"""Build a LaTeX appendix from the visualization manifest."""

from __future__ import annotations

import argparse
import csv
import os
from collections import OrderedDict
from pathlib import Path


CATEGORY_TITLES = {
    "overall": "Genel Model Görselleri",
    "language_summary": "Dil Bazlı Özet Görselleri",
    "detailed_distributions": "Ayrıntılı Metrik Dağılımları",
    "tradeoffs_scatter": "Trade-off ve Yoğunluk Grafikleri",
    "sample_pairwise": "Sample Bazlı Model Karşılaştırmaları",
    "interactive": "İnteraktif HTML Görselleri",
    "cross_run": "Koşular Arası Stabilite Görselleri",
}

CATEGORY_DESCRIPTIONS = {
    "overall": (
        "Bu görseller model seviyesindeki makro ortalamaları, metrik sıralamalarını, "
        "radar profillerini ve temel performans trade-offlarını gösterir."
    ),
    "language_summary": (
        "Bu görseller dil-model özet tablolarından türetilmiştir; her dilde hangi "
        "modelin hangi metrikte öne çıktığını ve modeller arasındaki dil bazlı farkları "
        "okumayı kolaylaştırır."
    ),
    "detailed_distributions": (
        "Bu görseller detailed_metrics satırlarını kullanır; sample seviyesinde dağılım, "
        "kümülatif dağılım ve metrik korelasyonlarını gösterir."
    ),
    "tradeoffs_scatter": (
        "Bu görseller iki metrik arasındaki ilişkiyi scatter ve hexbin yoğunluk "
        "görünümleriyle inceler; uzunluk, hız, kalite ve kaynak bağlılığı arasındaki "
        "dengeyi yorumlamak için kullanılır."
    ),
    "sample_pairwise": (
        "Bu görseller aynı sample üzerinde modellerin doğrudan karşılaştırılmasından "
        "türetilmiştir; kazanma oranları ve model fark dağılımlarını gösterir."
    ),
    "interactive": (
        "Bu bölüm PNG olarak gömülemeyen interaktif HTML görsellere bağlantılar verir. "
        "HTML dosyaları tarayıcıda açıldığında hover, zoom ve filtreleme gibi etkileşimli "
        "inceleme olanakları sunar."
    ),
    "cross_run": (
        "Bu görseller 200 örnek koşusu ile tam koşu arasındaki stabiliteyi gösterir; "
        "metriklerin ve dil-model skorlarının koşu boyutu değiştiğinde ne kadar oynadığını "
        "incelemek için kullanılır."
    ),
}

RUN_TITLES = {
    "xlsum_eval_200": "XL-Sum 200 Örnek Koşusu",
    "xlsum_eval_full": "XL-Sum Tam Değerlendirme Koşusu",
    "cross_run": "Koşular Arası Karşılaştırma",
}


def latex_escape(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(ch, ch) for ch in text)


def sentence_case(text: str) -> str:
    text = text.strip()
    if not text:
        return text
    return text[0].upper() + text[1:]


def normalize_text(text: str) -> str:
    text = text.replace("_", " ")
    text = text.replace("heatmap", "isi haritasi")
    text = text.replace("grouped bar", "gruplanmis cubuk grafigi")
    text = text.replace("radar", "radar grafigi")
    text = text.replace("scatter", "scatter grafigi")
    text = text.replace("pairplot", "ikili metrik matrisi")
    text = text.replace("win-rate", "kazanma orani")
    text = text.replace("win rate", "kazanma orani")
    text = text.replace("delta", "fark")
    text = text.replace("metric", "metrik")
    text = text.replace("metrics", "metrikler")
    text = text.replace("overall", "genel")
    text = text.replace("language", "dil")
    text = text.replace("model", "model")
    text = text.replace("sample", "sample")
    text = text.replace("Detailed", "Ayrintili")
    text = text.replace("Core", "Cekirdek")
    replacements = {
        "Classical": "Klasik",
        "classical": "klasik",
        "Capability": "Kabiliyet",
        "capability": "kabiliyet",
        "Quality": "Kalite",
        "quality": "kalite",
        "Behavior": "Davranış",
        "behavior": "davranış",
        "Efficiency": "Verimlilik",
        "efficiency": "verimlilik",
        "Language": "Dil",
        "language": "dil",
        "Interactive": "İnteraktif",
        "interactive": "interaktif",
        "Overall": "Genel",
        "overall": "genel",
        "macro summary": "makro özet",
        "grounding": "kaynak bağlılığı",
        "detailed": "ayrıntılı",
        "core": "çekirdek",
        "Sikistirma": "Sıkıştırma",
        "sikistirma": "sıkıştırma",
        "Tum": "Tüm",
        "Ayrintili": "Ayrıntılı",
        "Cekirdek": "Çekirdek",
        "isi": "ısı",
        "haritasi": "haritası",
        "gruplanmis": "gruplanmış",
        "cubuk": "çubuk",
        "grafigi": "grafiği",
        "uzerinden": "üzerinden",
        "bazli": "bazlı",
        "siralamalarini": "sıralamalarını",
        "gosterir": "gösterir",
        "gorunumu": "görünümü",
        "gorunumleriyle": "görünümleriyle",
        "gorseller": "görseller",
        "gorsel": "görsel",
        "karsilastirir": "karşılaştırır",
        "karsilastirma": "karşılaştırma",
        "dagilimlari": "dağılımları",
        "dagilimi": "dağılımı",
        "dagilim": "dağılım",
        "kumulatif": "kümülatif",
        "olceklenmis": "ölçeklenmiş",
        "ornek": "örnek",
        "kosusu": "koşusu",
        "kosular": "koşular",
        "arasi": "arası",
        "farklari": "farkları",
        "oranlari": "oranları",
        "baglantilari": "bağlantıları",
        "tiklanabilir": "tıklanabilir",
        "gomulemeyen": "gömülemeyen",
        "gomulmustur": "gömülmüştür",
        "verilmistir": "verilmiştir",
        "uretilmistir": "üretilmiştir",
        "uretilen": "üretilen",
        "baslik": "başlık",
        "aciklama": "açıklama",
        "klasorunde": "klasöründe",
        "tamamini": "tamamını",
        "donusturulmus": "dönüştürülmüş",
        "satirlarini": "satırlarını",
        "satirlarini": "satırlarını",
        "satırlarini": "satırlarını",
        "degerlendirme": "değerlendirme",
        "gore": "göre",
        "gorunur": "görünür",
        "karsilastirilmasindan": "karşılaştırılmasından",
        "turetilmistir": "türetilmiştir",
        "dogrudan": "doğrudan",
        "ayni": "aynı",
        "seviyesinde": "seviyesinde",
        "arasindaki": "arasındaki",
        "iliskisini": "ilişkisini",
        "iliskiyi": "ilişkiyi",
        "yogunluk": "yoğunluk",
        "hiz": "hız",
        "bagliligi": "bağlılığı",
        "dengeyi": "dengeyi",
        "yorumlamak": "yorumlamak",
        "icin": "için",
        "kullanilir": "kullanılır",
        "metrik": "metrik",
        "run": "koşu",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = text.replace("radar grafiği grafikte", "radar grafiğinde")
    text = text.replace("scatter grafiği olarak", "scatter olarak")
    return sentence_case(text)


def caption(title: str, description: str) -> str:
    title = normalize_text(title)
    description = normalize_text(description)
    return latex_escape(f"{title}. {description}")


def relpath_for_latex(path: str, report_dir: Path) -> str:
    source = Path(path)
    if not source.is_absolute():
        source = Path.cwd() / source
    rel = os.path.relpath(source, report_dir)
    return rel.replace(os.sep, "/")


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def grouped_rows(rows: list[dict[str, str]]) -> OrderedDict[str, OrderedDict[str, list[dict[str, str]]]]:
    grouped: OrderedDict[str, OrderedDict[str, list[dict[str, str]]]] = OrderedDict()
    for row in rows:
        grouped.setdefault(row["run"], OrderedDict()).setdefault(row["category"], []).append(row)
    return grouped


def write_appendix(rows: list[dict[str, str]], output: Path, report_dir: Path) -> None:
    groups = grouped_rows(rows)
    lines: list[str] = [
        "% Auto-generated by evaluation/build_visualization_appendix.py",
        r"\section{Görselleştirme Eki}",
        "",
        (
            "Bu ek, \\texttt{evaluation/eval\\_visualizations} klasöründe üretilen "
            "görsellerin tamamını rapora ekler. Statik PNG görseller PDF içine gömülmüştür; "
            "interaktif HTML görseller ise tıklanabilir bağlantı olarak verilmiştir. "
            "Her görselin açıklaması \\texttt{visualization\\_manifest.csv} dosyasındaki "
            "başlık ve açıklama alanlarından üretilmiştir."
        ),
        "",
    ]

    png_count = 0
    html_count = 0
    for run, categories in groups.items():
        lines.extend([r"\clearpage", rf"\subsection{{{latex_escape(RUN_TITLES.get(run, run))}}}", ""])
        for category, items in categories.items():
            title = CATEGORY_TITLES.get(category, category)
            description = CATEGORY_DESCRIPTIONS.get(category, "")
            lines.extend([rf"\subsubsection{{{latex_escape(title)}}}", latex_escape(description), ""])
            html_items = [row for row in items if Path(row["path"]).suffix.lower() == ".html"]
            png_items = [row for row in items if Path(row["path"]).suffix.lower() == ".png"]

            for row in png_items:
                png_count += 1
                rel = relpath_for_latex(row["path"], report_dir)
                lines.extend(
                    [
                        r"\begin{figure}[p]",
                        r"\centering",
                        rf"\includegraphics[width=\textwidth,height=0.72\textheight,keepaspectratio]{{{rel}}}",
                        rf"\caption{{{caption(row['title'], row['description'])}}}",
                        r"\end{figure}",
                        r"\clearpage",
                        "",
                    ]
                )

            if html_items:
                html_count += len(html_items)
                lines.extend([r"\paragraph{İnteraktif HTML bağlantıları}", r"\begin{itemize}"])
                for row in html_items:
                    rel = relpath_for_latex(row["path"], report_dir)
                    text = caption(row["title"], row["description"])
                    lines.append(rf"\item \href{{{rel}}}{{{text}}}")
                lines.extend([r"\end{itemize}", ""])

    lines.append(rf"% Included static PNG figures: {png_count}")
    lines.append(rf"% Linked interactive HTML files: {html_count}")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("evaluation/eval_visualizations/visualization_manifest.csv"),
        help="Visualization manifest CSV.",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path("evaluation/xlsum_eval_full"),
        help="Directory where the main LaTeX report is compiled.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/xlsum_eval_full/visualizations_appendix.tex"),
        help="Output appendix .tex path.",
    )
    args = parser.parse_args()
    rows = read_manifest(args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_appendix(rows, args.output, args.report_dir.resolve())
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
