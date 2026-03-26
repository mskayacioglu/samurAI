# Summarization Evaluation Report

Bu rapor model ortalama skorlarini listeler.

| Model | Capability Overall | ROUGE-L F1 | BLEU | Latency (s) | Compression |
|---|---:|---:|---:|---:|---:|
| mbart50_xlsum | 0.5992 | 0.1814 | 0.0460 | 0.009 | 20.16 |
| bart_base_cnn | 0.5523 | 0.2572 | 0.1031 | 1.895 | 17.09 |
| bart_reuters | 0.5404 | 0.1594 | 0.0238 | 0.874 | 46.16 |
| bart_large_cnn | 0.4853 | 0.1814 | 0.0460 | 12.224 | 20.16 |

## Capability Proxies (0-1)

- `capability_coherence`: cumle akis duzeni + dusuk tekrar + uygun cumle uzunlugu
- `capability_accuracy`: referans tabanli skorlar (ROUGE-L/BLEU/METEOR-lite) + kaynak kapsama
- `capability_clarity`: okunabilirlik (EN icin Flesch) + tekrar cezasi
- `capability_relevance`: ROUGE-1 recall (varsa) + kaynak kelime geri cagirim
- `capability_efficiency`: gecikme ve sikistirma oraninin bilesimi
- `quality_factuality`: kaynakla tutarlilik (kapsama + extractive fragment)
- `quality_completeness`: referans geri cagirim + uzunluk uyumu

Not: Bu capability skorlar dogrudan benchmark degil, insan-merkezli kriterlere yaklasik proxy degerlerdir.