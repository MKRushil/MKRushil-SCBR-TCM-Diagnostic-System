# Benchmark Report (v2.1)
- run_id: 20260131_0620
- profile: SCBR-Standard
- dataset: batch_list
- cases: 100
- turns_per_case: 3
- generated_at: 2026-01-31T16:16:50.020413

## 1. Profile Configuration Snapshot
| key | value |
|---|---|
| ENABLE_MULTI_TURN | True |
| ENABLE_REPAIR | True |
| ENABLE_RERANK | False |
| HYBRID_ALPHA | 1.0 |
| CASE_TOPK | 10 |
| BASELINE_MODE | none |
| SAFETY_STRICT_LEVEL | 1 |

## 2. Turn-wise Summary (mean over cases)
| turn | TCRS_avg | Confidence_avg | AmbiguityRatio_avg | RetrievalValid_rate | SafetyOk_rate |
|---:|---:|---:|---:|---:|---:|
| 1 | 0.64 | 0.68 | 0.00 | 0.00 | 1.00 |
| 2 | 0.63 | 0.67 | 0.00 | 0.00 | 1.00 |
| 3 | 0.64 | 0.68 | 0.00 | 0.00 | 1.00 |

## 3. v2.1 Metrics (macro)
| metric_id | metric_name | value | note |
|---|---|---:|---|
| M0_TCRS_Avg | ... | 0.6366 | - |
| M0_TCRS_Final | ... | 0.6370 | - |
| M1_Slope | ... | -0.0007 | - |
| M1b_A1_Slope | ... | 0.0097 | - |
| M2_TTS' | ... | 1.4100 | - |
| M3_ARR | ... | 0.0000 | - |
| M4_RAHR | ... | 0.0000 | - |
| M5_RDRR | ... | N/A | - |
| M6_A1' | ... | 0.4723 | - |
| M7_Coverage | ... | 0.3768 | - |
| M8_FailSafeRate | ... | N/A | - |
| M9_CCAR | ... | 1.0000 | - |
| M10_HER | ... | 0.0000 | - |

## 4. Error / Exception Log
- parsing_errors: 0 (Placeholder)

## 5. Notes
- ambiguity_ratio is cumulative-intersection (monotonic non-increasing)
- baseline_single_turn only evaluates turn=1 by design
