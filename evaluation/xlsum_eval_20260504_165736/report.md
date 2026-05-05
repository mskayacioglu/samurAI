# XL-Sum Evaluation Report

Generated at: `2026-05-04T17:55:48.952786`
Run directory: `/content/drive/MyDrive/inf494_projet/evaluation/xlsum_eval_runs/xlsum_eval_20260504_165736`
Dataset: `csebuetnlp/xlsum`, split: `test`
Device: `cuda`
Max samples per language: `200`

## Overall Model Macro Summary

| model | model_scope | languages | samples | capability_overall_mean | capability_coherence_mean | capability_accuracy_mean | capability_clarity_mean | capability_relevance_mean | capability_efficiency_mean | rougeL_fmeasure_mean | bleu_mean | meteor_lite_mean | latency_seconds_mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mt5-xlsum | multilingual | 11 | 2200 | 0.6616 | 0.9747 | 0.4303 | 0.9134 | 0.2674 | 0.7221 | 0.3004 | 0.1302 | 0.3205 | 0.2592 |
| mbart-xlsum-2 | multilingual | 11 | 2200 | 0.6563 | 0.9594 | 0.4154 | 0.8938 | 0.2734 | 0.7395 | 0.2806 | 0.1239 | 0.3210 | 0.1893 |
| mbart50_xlsum | multilingual | 11 | 2200 | 0.6559 | 0.9607 | 0.4216 | 0.8889 | 0.2723 | 0.7360 | 0.2779 | 0.1191 | 0.3178 | 0.2003 |

## Language / Model Summary

| language | xlsum_subset | model | samples | capability_overall_mean | rouge1_fmeasure_mean | rouge2_fmeasure_mean | rougeL_fmeasure_mean | bleu_mean | meteor_lite_mean |
|---|---|---|---|---|---|---|---|---|---|
| ar | arabic | mbart-xlsum-2 | 200 | 0.6371 | 0.2828 | 0.1243 | 0.2336 | 0.0860 | 0.2428 |
| ar | arabic | mbart50_xlsum | 200 | 0.6366 | 0.2803 | 0.1148 | 0.2299 | 0.0748 | 0.2362 |
| ar | arabic | mt5-xlsum | 200 | 0.6361 | 0.2992 | 0.1337 | 0.2486 | 0.0860 | 0.2483 |
| en | english | mbart50_xlsum | 200 | 0.6217 | 0.3411 | 0.1289 | 0.2761 | 0.0909 | 0.2945 |
| en | english | mbart-xlsum-2 | 200 | 0.6217 | 0.3462 | 0.1234 | 0.2730 | 0.0908 | 0.2989 |
| en | english | mt5-xlsum | 200 | 0.6190 | 0.3463 | 0.1296 | 0.2774 | 0.0894 | 0.2873 |
| es | spanish | mt5-xlsum | 200 | 0.6755 | 0.3160 | 0.1188 | 0.2462 | 0.0772 | 0.2538 |
| es | spanish | mbart-xlsum-2 | 200 | 0.6727 | 0.2982 | 0.1051 | 0.2277 | 0.0726 | 0.2445 |
| es | spanish | mbart50_xlsum | 200 | 0.6689 | 0.2938 | 0.0946 | 0.2228 | 0.0642 | 0.2379 |
| fr | french | mbart-xlsum-2 | 200 | 0.6474 | 0.3278 | 0.1454 | 0.2679 | 0.1034 | 0.2825 |
| fr | french | mt5-xlsum | 200 | 0.6471 | 0.3329 | 0.1543 | 0.2782 | 0.0981 | 0.2767 |
| fr | french | mbart50_xlsum | 200 | 0.6455 | 0.3151 | 0.1347 | 0.2551 | 0.0908 | 0.2742 |
| hi | hindi | mt5-xlsum | 200 | 0.6520 | 0.5748 | 0.3129 | 0.4223 | 0.2279 | 0.5134 |
| hi | hindi | mbart-xlsum-2 | 200 | 0.6514 | 0.5757 | 0.3046 | 0.4134 | 0.2301 | 0.5403 |
| hi | hindi | mbart50_xlsum | 200 | 0.6459 | 0.5749 | 0.2925 | 0.4102 | 0.2204 | 0.5438 |
| ja | japanese | mt5-xlsum | 200 | 0.6922 | 0.5374 | 0.3477 | 0.3924 | 0.2406 | 0.4734 |
| ja | japanese | mbart50_xlsum | 200 | 0.6810 | 0.5046 | 0.3067 | 0.3540 | 0.2163 | 0.4516 |
| ja | japanese | mbart-xlsum-2 | 200 | 0.6776 | 0.5114 | 0.3133 | 0.3613 | 0.2250 | 0.4599 |
| ko | korean | mt5-xlsum | 200 | 0.7330 | 0.4589 | 0.2689 | 0.3749 | 0.1894 | 0.4145 |
| ko | korean | mbart50_xlsum | 200 | 0.7225 | 0.4193 | 0.2363 | 0.3305 | 0.1692 | 0.3987 |
| ko | korean | mbart-xlsum-2 | 200 | 0.7225 | 0.4260 | 0.2360 | 0.3340 | 0.1729 | 0.4125 |
| ru | russian | mbart50_xlsum | 200 | 0.6426 | 0.2428 | 0.0963 | 0.2028 | 0.0642 | 0.1929 |
| ru | russian | mt5-xlsum | 200 | 0.6400 | 0.2585 | 0.1094 | 0.2226 | 0.0718 | 0.2016 |
| ru | russian | mbart-xlsum-2 | 200 | 0.6350 | 0.2444 | 0.0943 | 0.2039 | 0.0623 | 0.1955 |
| tr | turkish | mt5-xlsum | 200 | 0.6242 | 0.2483 | 0.1204 | 0.2291 | 0.0796 | 0.2108 |
| tr | turkish | mbart50_xlsum | 200 | 0.6216 | 0.2391 | 0.1103 | 0.2125 | 0.0767 | 0.2148 |
| tr | turkish | mbart-xlsum-2 | 200 | 0.6212 | 0.2422 | 0.1094 | 0.2157 | 0.0766 | 0.2179 |
| vi | vietnamese | mt5-xlsum | 200 | 0.6474 | 0.3222 | 0.1571 | 0.2520 | 0.0885 | 0.2652 |
| vi | vietnamese | mbart-xlsum-2 | 200 | 0.6402 | 0.3275 | 0.1598 | 0.2516 | 0.0950 | 0.2862 |
| vi | vietnamese | mbart50_xlsum | 200 | 0.6385 | 0.3275 | 0.1565 | 0.2530 | 0.0915 | 0.2861 |
| zh | chinese_simplified | mt5-xlsum | 200 | 0.7108 | 0.4248 | 0.2751 | 0.3607 | 0.1843 | 0.3802 |
| zh | chinese_simplified | mbart-xlsum-2 | 200 | 0.6924 | 0.3764 | 0.2217 | 0.3042 | 0.1480 | 0.3499 |
| zh | chinese_simplified | mbart50_xlsum | 200 | 0.6898 | 0.3859 | 0.2285 | 0.3096 | 0.1509 | 0.3655 |

## Skipped Languages

| language   | language_name   | xlsum_subset   | status                  |
|:-----------|:----------------|:---------------|:------------------------|
| de         | German          | german         | skipped_no_xlsum_subset |
| it         | Italian         | italian        | skipped_no_xlsum_subset |
| nl         | Dutch           | dutch          | skipped_no_xlsum_subset |
| ro         | Romanian        | romanian       | skipped_no_xlsum_subset |

## Metric Formulas

| metric             | paper_question                                                                          | operational_proxy                                                                                   | formula                                                                                                                                  |
|:-------------------|:----------------------------------------------------------------------------------------|:----------------------------------------------------------------------------------------------------|:-----------------------------------------------------------------------------------------------------------------------------------------|
| coherence          | Does the metric use prompts and formats resembling genuine human interaction?           | Generated summary flow: balanced sentence rhythm, low repeated 3-grams, reasonable sentence length. | 0.50*(1 - min(sentence_len_std/20, 1)) + 0.30*(1 - repetition_3gram) + 0.20*ideal_sentence_length_score                                  |
| accuracy           | Is the information verifiably correct against trusted sources or gold-standard answers? | Reference agreement plus source grounding proxy.                                                    | ref_acc=mean(rougeL_fmeasure, bleu, meteor_lite); 0.70*ref_acc + 0.30*source_coverage                                                    |
| clarity            | Does the metric measure whether outputs are easy to understand and clearly worded?      | Readability/sentence simplicity plus low repetition.                                                | 0.70*readability_component + 0.30*(1 - repetition_3gram)                                                                                 |
| relevance          | Does the benchmark test a broad and meaningful range within the capability domain?      | Reference recall and source-term recall for the summary.                                            | 0.70*rouge1_recall + 0.30*source_recall                                                                                                  |
| efficiency         | Does the metric reflect time or cognitive effort saved?                                 | Generation latency normalized by input length plus compression usefulness.                          | latency_score=1/(1+latency_per_1k_tokens); compression_score=clip((compression_ratio-2)/18); 0.60*latency_score + 0.40*compression_score |
| capability_overall | Aggregate human-centered utility score.                                                 | Macro score across the five Section 2.4 dimensions.                                                 | mean(coherence, accuracy, clarity, relevance, efficiency)                                                                                |

## Notes

- Section 2.4 scores are automatic proxies, not human annotation.
- `accuracy` combines gold-summary overlap and source grounding; it does not prove factual truth by itself.
- `efficiency` depends on current Colab hardware load, batch size, and generation settings.
- German, Italian, Dutch, and Romanian are kept in the selected 15-language plan, but the public `csebuetnlp/xlsum` release does not provide matching subsets; use a local held-out eval file for those if needed.