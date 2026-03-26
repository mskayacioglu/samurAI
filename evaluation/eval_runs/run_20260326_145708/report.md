# Summarization Evaluation Report

Bu rapor model ortalama skorlarini listeler.

| Model | Capability Overall | ROUGE-L F1 | BLEU | Latency (s) | Compression |
|---|---:|---:|---:|---:|---:|
| bart_reuters | 0.5562 | 0.3810 | 0.0521 | 3.307 | 1.00 |

## Capability Proxies (0-1)

- `capability_coherence`: cumle akis duzeni + dusuk tekrar + uygun cumle uzunlugu
- `capability_accuracy`: referans tabanli skorlar (ROUGE-L/BLEU/METEOR-lite) + kaynak kapsama
- `capability_clarity`: okunabilirlik (EN icin Flesch) + tekrar cezasi
- `capability_relevance`: ROUGE-1 recall (varsa) + kaynak kelime geri cagirim
- `capability_efficiency`: gecikme ve sikistirma oraninin bilesimi
- `quality_factuality`: kaynakla tutarlilik (kapsama + extractive fragment)
- `quality_completeness`: referans geri cagirim + uzunluk uyumu

Not: Bu capability skorlar dogrudan benchmark degil, insan-merkezli kriterlere yaklasik proxy degerlerdir.