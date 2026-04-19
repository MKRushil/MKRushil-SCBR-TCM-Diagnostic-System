import httpx
import json
import time
import requests
import uuid
import sys
import os
import csv
import asyncio
import argparse
import numpy as np
from datetime import datetime
from dotenv import load_dotenv
from collections import defaultdict

# Load env
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.core.config import get_settings
from app.evaluation.scbr_evaluator import SCBREvaluator

settings = get_settings()
API_URL = "http://localhost:8000/api/v1/chat"

async def get_embedding_for_benchmark(text):
    if not text: return None
    try:
        url = "https://integrate.api.nvidia.com/v1/embeddings"
        headers = {
            "Authorization": f"Bearer {settings.NVIDIA_EMBEDDING_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        payload = {
            "model": settings.EMBEDDING_MODEL_NAME,
            "input": [text],
            "input_type": "query",
            "encoding_format": "float"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            return data['data'][0]['embedding']
            
    except Exception as e:
        print(f"Error getting embedding for '{str(text)[:10]}...': {e}")
        import traceback
        traceback.print_exc()
        return None

async def run_benchmark_task(dataset_path, output_dir, profile_name, run_id, scenario):
    print(f"Starting SCBR Benchmark task (Profile: {profile_name}, Dataset: {dataset_path})...")
    
    if not os.path.exists(dataset_path):
        print(f"Error: Dataset not found at {dataset_path}")
        return

    with open(dataset_path, 'r', encoding='utf-8') as f:
        data_blob = json.load(f)
        if isinstance(data_blob, list):
            cases = data_blob
            dataset_id = "batch_list"
        else:
            cases = data_blob.get('cases', [])
            dataset_id = data_blob.get('id', 'unknown')

    evaluator = SCBREvaluator()
    
    all_turn_rows = []      
    all_case_summaries = [] 
    all_logs = []           

    for case in cases: # Process all cases
        case_id = case.get('id') or case.get('case_id')
        category = case.get('category', 'Uncategorized')
        session_id = f"bench_{uuid.uuid4().hex[:8]}"
        print(f"\n--- Processing Case: {case_id} ({category}) ---")
        
        # Prepare GT (FIX: Read from nested 'gold' field and dynamic gt_vector calculation)
        gold_data = case.get('gold', {})
        gt_diag = gold_data.get('syndrome', '')
        gt_attr = gold_data.get('attributes', {})
        gt_vector = case.get('gt_vector', []) 
        
        # [V3.1 FIX] Dynamic GT Vector Generation if missing
        if not gt_vector and gt_diag:
             print(f"  [Info] Generating GT Vector for '{gt_diag}'...")
             gt_text = f"{gt_diag} {json.dumps(gt_attr, ensure_ascii=False)}"
             gt_vector = await get_embedding_for_benchmark(gt_text)


        # Handle different dataset structures (turns vs single turn)
        turns = case.get('turns', [])
        
        # If baseline_single_turn, we might only want the first turn, or the system might ignore history.
        # But here we simulate the client sending requests.
        # test.md says: "baseline_single_turn (Baseline-A: single-turn RAG，保留向量檢索，但不做多回合/修補/收斂)"
        # "每个 case 固定 3 turns（若 baseline_single_turn，只送 turn1，其它 turns 忽略）"
        
        target_turns = turns[:3] # Limit to 3 turns
        if settings.BASELINE_MODE == 'single_turn':
             target_turns = turns[:1]

        case_logs = [] 
        case_turn_metrics = [] 
        
        # Ambiguity State Tracking
        cumulative_ambiguity_set = set()
        A0_count = 0 

        for turn_idx, turn in enumerate(target_turns):
            turn_id = turn_idx + 1 
            user_input = turn.get('user_text', turn.get('input', ""))
            
            # expected_action for bad cases
            expected_action = turn.get('expected_system_action') or turn.get('expected_action', '')
            
            # Use turn-specific GT if available, else case-level
            turn_gt_diag = turn.get('gold', {}).get('syndrome', gt_diag)
            turn_is_emergency = turn.get('is_emergency', case.get('is_emergency', False))

            print(f"  Turn {turn_id}: Input='{user_input[:30]}...' -> ", end="", flush=True)
            
            payload = {
                "session_id": session_id,
                "patient_id": "benchmark_patient",
                "message": user_input,
                "test_mode_flags": {
                    "BASELINE_MODE": settings.BASELINE_MODE
                }
            }
            
            start_time = time.time()
            try:
                resp = requests.post(API_URL, json=payload)
                latency_ms = int((time.time() - start_time) * 1000)
                
                if resp.status_code == 200:
                    data = resp.json()
                    
                    # Extraction
                    pred_type = data.get('response_type', 'FALLBACK')
                    pred_diag = ""
                    pred_conf = 0.0
                    
                    if data.get('diagnosis_list'):
                        top1 = data['diagnosis_list'][0]
                        pred_diag = top1.get('disease_name', "")
                        pred_conf = top1.get('confidence', 0.0)
                    
                    pred_attributes = {}
                    if data.get('diagnosis_list'):
                        pred_attributes = top1.get('pred_attributes', {})

                    pred_risk = data.get('risk_level', 'GREEN')
                    
                    # Cumulative Ambiguity Logic
                    std_features = data.get('standardized_features') or {}
                    raw_ambiguous_terms = std_features.get('ambiguous_terms', [])
                    raw_ambiguity_set = set(raw_ambiguous_terms)
                    
                    if turn_id == 1:
                        cumulative_ambiguity_set = raw_ambiguity_set
                        A0_count = max(len(cumulative_ambiguity_set), 1)
                    else:
                        cumulative_ambiguity_set = cumulative_ambiguity_set.intersection(raw_ambiguity_set)
                    
                    amb_count_cum = len(cumulative_ambiguity_set)
                    
                    # [V3.1] A1 Metric Optimization
                    # GT Vector is generated from: "{gt_diag} {gt_attr_json}"
                    # Pred Vector should match this format to ensure valid Cosine Similarity.
                    # Using full formatted_report (long text) vs GT (short text) dilutes similarity.
                    
                    if pred_diag:
                         pred_vector_text = f"{pred_diag} {json.dumps(pred_attributes, ensure_ascii=False)}"
                    else:
                         # Fallback if structured data is missing (e.g. pure conversational response)
                         pred_vector_text = data.get('formatted_report', "")
                         
                    pred_vector = await get_embedding_for_benchmark(pred_vector_text) 
                    retrieved_context = data.get('retrieved_context', []) 

                    # Prepare Log Object (Extended for internal usage)
                    turn_data = {
                        "case_id": case_id,
                        "category": category,
                        "turn": turn_id, 
                        "input_text": user_input,
                        "gt_diagnosis": turn_gt_diag,
                        "gt_attributes": gt_attr,
                        "gt_vector": gt_vector, 
                        "is_emergency_gt": turn_is_emergency,
                        
                        "pred_response_type": pred_type,
                        "pred_diagnosis": pred_diag,
                        "pred_confidence": pred_conf,
                        "pred_attributes": pred_attributes, 
                        "pred_vector": pred_vector,
                        "pred_risk_level": pred_risk,
                        "ambiguous_terms_count": amb_count_cum, # Cumulative
                        "retrieved_context": retrieved_context, 
                    }
                    
                    # Metrics Calculation
                    metrics = evaluator.calculate_turn_metrics(turn_data, A0_count)
                    
                    # A1 Prime calculation for turn
                    a1_prime = 0.0
                    if pred_vector and gt_vector:
                         a1_prime = evaluator.calculate_a1_prime(pred_vector, gt_vector, pred_diag, turn_gt_diag)
                    
                    turn_data['a1_prime'] = a1_prime

                    case_turn_metrics.append(metrics)
                    case_logs.append(turn_data)
                    all_logs.append({**turn_data, "metrics": metrics}) 
                    
                    # CSV Row Construction (Aligned with test.md)
                    flat_row = {
                        "run_id": run_id,
                        "profile": profile_name,
                        "dataset_id": dataset_id,
                        "scenario": scenario,
                        "case_id": case_id,
                        "turn": turn_id,
                        "user_text": user_input[:120],
                        "expected_action": expected_action,
                        "system_action": pred_type, # approximating system_action with response_type
                        "confidence": pred_conf,
                        "ambiguity_count_raw": len(raw_ambiguity_set),
                        "ambiguity_count_cum": amb_count_cum,
                        "ambiguity_ratio": metrics['A_Ambiguity_Ratio'],
                        "retrieval_valid": int(metrics['R_Retrieval']),
                        "safety_ok": int(metrics['S_Safety']),
                        "tcrs": metrics['TCRS'],
                        "a1_prime": a1_prime,
                        "latency_ms": latency_ms
                    }
                    all_turn_rows.append(flat_row)
                    
                    print(f"[{pred_type}] {pred_diag} (Conf: {pred_conf:.2f}) | TCRS: {metrics['TCRS']:.4f}")
                    
                else:
                    print(f"Error {resp.status_code}")

            except Exception as e:
                print(f"Exception: {str(e)}")
        
        # Evaluate Session (Case Level)
        session_metrics = evaluator.evaluate_session(case_logs, case_turn_metrics)
        
        # CSV Case Row Construction
        # Ensure we have 3 turns for tcrs columns even if single turn mode
        tcrs_vals = [tm['TCRS'] for tm in case_turn_metrics]
        while len(tcrs_vals) < 3:
            tcrs_vals.append(None) # Fill with None
        
        # Notes
        notes = ""
        
        # RDRR Flag: degraded cases only: TCRS_final > TCRS_first
        rdrr_flag = "NA"
        if scenario == "degraded_retrieval":
             if session_metrics['M0_TCRS_Final'] > tcrs_vals[0]:
                 rdrr_flag = 1
             else:
                 rdrr_flag = 0

        # Failsafe Match
        failsafe_match = "NA"
        if scenario == "adversarial" or dataset_id == "bad":
             # Logic to check if system action matches expected_outcome
             # Assuming last turn's action matters
             last_action = case_logs[-1]['pred_response_type'] if case_logs else ""
             # Need expected outcome from case? Or turns?
             # test.md: "FailSafeRate = (# cases where system action matches gold.expected_outcome)"
             expected = case.get('expected_outcome') or case.get('expected_system_action')
             if expected:
                 if last_action == expected:
                     failsafe_match = 1
                 elif expected == "fail_safe_or_ask_more" and last_action in ["EMERGENCY_ABORT", "FALLBACK", "INQUIRY_ONLY"]:
                     failsafe_match = 1
                 else:
                     failsafe_match = 0
        
        case_row = {
            "run_id": run_id,
            "profile": profile_name,
            "dataset_id": dataset_id,
            "scenario": scenario,
            "case_id": case_id,
            "turns": 3,
            "tcrs_t1": tcrs_vals[0] if tcrs_vals[0] is not None else "",
            "tcrs_t2": tcrs_vals[1] if tcrs_vals[1] is not None else "",
            "tcrs_t3": tcrs_vals[2] if tcrs_vals[2] is not None else "",
            "tcrs_final": session_metrics.get('M0_TCRS_Final', ""),
            "slope": session_metrics.get('M1_Convergence_Slope', ""),
            "a1_slope": session_metrics.get('M1b_A1_Slope', ""),  # [V3.1] NEW: A1' Slope
            "tts": session_metrics.get('M2_TTS', ""),
            "arr": session_metrics.get('M3_ARR', ""),
            
            # M4-M6 (Outcome)
            # Old RAHR (M4) removed.
            # M4 = RDRR, M5 = A1, M6 = Coverage
            "rdrr_flag": rdrr_flag, # M4 (Flag derived from logic, or use Metric Value)
            "a1_prime": session_metrics.get('M5_A1_Prime', ""),
            "coverage": session_metrics.get('M6_Coverage', ""),
            
            # M7-M8 (Safety)
            "failsafe_match": failsafe_match, # M7
            "ccar_flag": int(session_metrics.get('M8_CCAR', 1.0)), # M8
            "her_flag": int(1.0 - session_metrics.get('M10_HER', 0.0)),
            "notes": notes
        }
        all_case_summaries.append(case_row)
        
        print(f"  => Case Finished.")

    # ==========================================
    # Reporting
    # ==========================================
    
    # 1. Profile Directory
    profile_dir = os.path.join(output_dir, profile_name)
    os.makedirs(profile_dir, exist_ok=True)

    # 2. CSV A: Turn-wise Metrics
    csv_turns_path = os.path.join(profile_dir, f"benchmark_turns_{profile_name}_{run_id}.csv")
    if all_turn_rows:
        keys = all_turn_rows[0].keys()
        with open(csv_turns_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(all_turn_rows)
    
    # 3. CSV B: Case Metrics
    csv_cases_path = os.path.join(profile_dir, f"benchmark_cases_{profile_name}_{run_id}.csv")
    if all_case_summaries:
        keys = all_case_summaries[0].keys()
        with open(csv_cases_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(all_case_summaries)

    # 4. Report MD
    # Calculate Macro Averages
    macro_metrics = {}
    if all_case_summaries:
        # Helper to safely get float
        def safe_float(rows, key):
            vals = [r[key] for r in rows if key in r and r[key] not in ["", "NA", None]]
            return float(np.mean(vals)) if vals else "N/A"

        macro_metrics["M0_TCRS_Avg"] = safe_float(all_case_summaries, "tcrs_final") # Using Final as proxy or calculate avg over all turns? test.md asks for both.
        # Recalculate Turn-wise Average TCRS from turns
        if all_turn_rows:
            all_tcrs = [r['tcrs'] for r in all_turn_rows if r['tcrs'] is not None]
            macro_metrics["M0_TCRS_Avg"] = float(np.mean(all_tcrs)) if all_tcrs else "N/A"
        
        macro_metrics["M0_TCRS_Final"] = safe_float(all_case_summaries, "tcrs_final")
        macro_metrics["M1_Slope"] = safe_float(all_case_summaries, "slope")
        macro_metrics["M1b_A1_Slope"] = safe_float(all_case_summaries, "a1_slope")  # [V3.1] NEW
        macro_metrics["M2_TTS'"] = safe_float(all_case_summaries, "tts")
        macro_metrics["M3_ARR"] = safe_float(all_case_summaries, "arr")
        # M4 RAHR - Calculate from retrieval_valid rate (any turn hit = success)
        rahr_values = [1 if r['retrieval_valid'] == 1 else 0 for r in all_turn_rows]
        if rahr_values:
            # Case-level: if ANY turn in a case has retrieval_valid=1, case RAHR=1
            case_rahr = {}
            for r in all_turn_rows:
                cid = r['case_id']
                if cid not in case_rahr:
                    case_rahr[cid] = 0
                if r['retrieval_valid'] == 1:
                    case_rahr[cid] = 1
            macro_metrics["M4_RAHR"] = float(np.mean(list(case_rahr.values()))) if case_rahr else "N/A"
        else:
            macro_metrics["M4_RAHR"] = "N/A"
        
        # M5 RDRR
        rdrr_flags = [r['rdrr_flag'] for r in all_case_summaries if r['rdrr_flag'] != "NA"]
        macro_metrics["M5_RDRR"] = float(np.mean(rdrr_flags)) if rdrr_flags else "N/A"
        
        # M6 A1' (From turns avg?)
        if all_turn_rows:
             a1s = [r['a1_prime'] for r in all_turn_rows if r['a1_prime']]
             macro_metrics["M6_A1'"] = float(np.mean(a1s)) if a1s else "N/A"
        
        # M7 Coverage - Use coverage from case_summaries
        coverage_vals = [r['coverage'] for r in all_case_summaries if r.get('coverage') not in [None, "", "N/A"]]
        macro_metrics["M7_Coverage"] = float(np.mean(coverage_vals)) if coverage_vals else "N/A"

        # M8 FailSafe
        fs_matches = [r['failsafe_match'] for r in all_case_summaries if r['failsafe_match'] != "NA"]
        macro_metrics["M8_FailSafeRate"] = float(np.mean(fs_matches)) if fs_matches else "N/A"

        # M9 CCAR
        ccars = [r['ccar_flag'] for r in all_case_summaries]
        macro_metrics["M9_CCAR"] = float(np.mean(ccars)) if ccars else "N/A"

        # M10 HER
        hers = [1 - r['her_flag'] for r in all_case_summaries] # her_flag is 1 if no hallucination
        macro_metrics["M10_HER"] = float(np.mean(hers)) if hers else "N/A"

    # Turn-wise Summary
    turn_summary = {}
    for t in [1, 2, 3]:
        rows = [r for r in all_turn_rows if r['turn'] == t]
        if rows:
            turn_summary[t] = {
                "TCRS_avg": float(np.mean([r['tcrs'] for r in rows])),
                "Confidence_avg": float(np.mean([r['confidence'] for r in rows])),
                "AmbiguityRatio_avg": float(np.mean([r['ambiguity_ratio'] for r in rows])),
                "RetrievalValid_rate": float(np.mean([r['retrieval_valid'] for r in rows])),
                "SafetyOk_rate": float(np.mean([r['safety_ok'] for r in rows]))
            }

    md_file_path = os.path.join(profile_dir, f"benchmark_report_{profile_name}_{run_id}.md")
    with open(md_file_path, 'w', encoding='utf-8') as f:
        f.write(f"# Benchmark Report (v2.1)\n")
        f.write(f"- run_id: {run_id}\n")
        f.write(f"- profile: {profile_name}\n")
        f.write(f"- dataset: {dataset_id}\n")
        f.write(f"- cases: {len(cases)}\n")
        f.write(f"- turns_per_case: 3\n")
        f.write(f"- generated_at: {datetime.now().isoformat()}\n\n")
        
        f.write("## 1. Profile Configuration Snapshot\n")
        f.write("| key | value |\n|---|---|\n")
        # List interesting settings
        for k in ["ENABLE_MULTI_TURN", "ENABLE_REPAIR", "ENABLE_RERANK", "HYBRID_ALPHA", "CASE_TOPK", "BASELINE_MODE", "SAFETY_STRICT_LEVEL"]:
            val = getattr(settings, k, "N/A")
            f.write(f"| {k} | {val} |\n")

        f.write("\n## 2. Turn-wise Summary (mean over cases)\n")
        f.write("| turn | TCRS_avg | Confidence_avg | AmbiguityRatio_avg | RetrievalValid_rate | SafetyOk_rate |\n")
        f.write("|---:|---:|---:|---:|---:|---:|\n")
        for t in sorted(turn_summary.keys()):
            s = turn_summary[t]
            f.write(f"| {t} | {s['TCRS_avg']:.2f} | {s['Confidence_avg']:.2f} | {s['AmbiguityRatio_avg']:.2f} | {s['RetrievalValid_rate']:.2f} | {s['SafetyOk_rate']:.2f} |\n")

        f.write("\n## 3. v2.1 Metrics (macro)\n")
        f.write("| metric_id | metric_name | value | note |\n|---|---|---:|---|\n")
        for k, v in macro_metrics.items():
            val_str = f"{v:.4f}" if isinstance(v, float) else str(v)
            f.write(f"| {k} | ... | {val_str} | - |\n")

        f.write("\n## 4. Error / Exception Log\n")
        f.write("- parsing_errors: 0 (Placeholder)\n")

        f.write("\n## 5. Notes\n")
        f.write("- ambiguity_ratio is cumulative-intersection (monotonic non-increasing)\n")
        f.write("- baseline_single_turn only evaluates turn=1 by design\n")

    print(f"[Done] Generated 3 artifacts in {profile_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--run_id", required=True)
    parser.add_argument("--scenario", required=True)
    args = parser.parse_args()
    
    asyncio.run(run_benchmark_task(args.dataset, args.outdir, args.profile, args.run_id, args.scenario))