# Benchmark Report (v2.1)
- run_id: 20260201_0158
- profile: Baseline-Combined
- dataset: batch_list
- cases: 100
- turns_per_case: 3
- generated_at: 2026-02-01T04:51:04.041610

## 1. Profile Configuration Snapshot
| key | value |
|---|---|
| ENABLE_MULTI_TURN | True |
| ENABLE_REPAIR | True |
| ENABLE_RERANK | False |
| HYBRID_ALPHA | 1.0 |
| CASE_TOPK | 10 |
| BASELINE_MODE | simple_rag |
| SAFETY_STRICT_LEVEL | 1 |

## 2. Turn-wise Summary (mean over cases)
| turn | TCRS_avg | Confidence_avg | AmbiguityRatio_avg | RetrievalValid_rate | SafetyOk_rate |
|---:|---:|---:|---:|---:|---:|
| 1 | 0.59 | 0.55 | 0.00 | 0.00 | 1.00 |
| 2 | 0.58 | 0.51 | 0.00 | 0.00 | 1.00 |
| 3 | 0.59 | 0.54 | 0.00 | 0.00 | 1.00 |

## 3. v2.1 Metrics (macro)
| metric_id | metric_name | value | note |
|---|---|---:|---|
| M0_TCRS_Avg | ... | 0.5872 | - |
| M0_TCRS_Final | ... | 0.5897 | - |
| M1_Slope | ... | -0.0011 | - |
| M1b_A1_Slope | ... | 0.0264 | - |
| M2_TTS' | ... | 1.9700 | - |
| M3_ARR | ... | 0.0000 | - |
| M4_RAHR | ... | 0.0000 | - |
| M5_RDRR | ... | N/A | - |
| M6_A1' | ... | 0.4418 | - |
| M7_Coverage | ... | 0.3612 | - |
| M8_FailSafeRate | ... | N/A | - |
| M9_CCAR | ... | 1.0000 | - |
| M10_HER | ... | 0.0000 | - |

## 4. Error / Exception Log
- parsing_errors: 0 (Placeholder)

## 5. Notes
- ambiguity_ratio is cumulative-intersection (monotonic non-increasing)
- baseline_single_turn only evaluates turn=1 by design
