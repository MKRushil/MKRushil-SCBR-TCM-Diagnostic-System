#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SCBR V3.1 Full-Scale Experiment Script
100 案例完整測試腳本 (僅 SCBR-Standard)

用法:
    python run_100_case_experiment.py
    python run_100_case_experiment.py --dataset custom.json --outdir custom_output
"""

import os
import subprocess
import time
import argparse
from datetime import datetime

# 配置內部路徑
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)

# 預設使用 merged_eval_normal.json (100 案例)
DEFAULT_DATASET = os.path.join(BASE_DIR, "merged_eval_normal.json")

def run_experiment(dataset_path: str, output_dir: str, run_id: str, scenario: str = "full_scale_100"):
    """執行 SCBR-Standard 實驗"""
    
    print(f"\n{'='*70}")
    print(f" SCBR V3.1 Full-Scale Experiment (100 Cases)")
    print(f"{'='*70}")
    print(f" Run ID: {run_id}")
    print(f" Dataset: {os.path.basename(dataset_path)}")
    print(f" Output: {output_dir}")
    print(f" Scenario: {scenario}")
    print(f"{'='*70}\n")
    
    # 準備環境變數 (SCBR-Standard)
    env = os.environ.copy()
    env["BASELINE_MODE"] = "none"
    env["USE_V31_PIPELINE"] = "true"
    env["PYTHONPATH"] = f"{ROOT_DIR};{os.path.join(ROOT_DIR, 'backend')}"
    
    # 確保輸出目錄存在
    os.makedirs(output_dir, exist_ok=True)
    
    # 構建命令
    benchmark_script = os.path.join(BASE_DIR, "run_benchmark.py")
    profile_name = "SCBR-Standard"
    
    cmd = [
        "python", benchmark_script,
        "--dataset", dataset_path,
        "--outdir", output_dir,
        "--profile", profile_name,
        "--run_id", run_id,
        "--scenario", scenario
    ]
    
    print(f"[INFO] 啟動 SCBR-Standard 實驗 (螺旋協商四步驟, Full Spiral SCBR)")
    print(f"[INFO] 預估時間: 100 案例 × 3 回合 × 30秒/回合 ≈ 150 分鐘")
    print(f"[INFO] 開始時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    start_time = time.time()
    
    try:
        subprocess.run(cmd, env=env, check=True)
        print(f"\n[SUCCESS] SCBR-Standard 100-case 實驗完成")
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] 實驗執行失敗: {e}")
        return 1
    
    duration = time.time() - start_time
    
    print(f"\n{'='*70}")
    print(f" 實驗完成！")
    print(f"{'='*70}")
    print(f" 總耗時: {duration/60:.1f} 分鐘")
    print(f" 結果目錄: {output_dir}")
    print(f" 請查看以下檔案:")
    print(f"   - benchmark_report_{profile_name}_{run_id}.md")
    print(f"   - benchmark_cases_{profile_name}_{run_id}.csv")
    print(f"   - benchmark_turns_{profile_name}_{run_id}.csv")
    print(f"{'='*70}\n")
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="SCBR V3.1 Full-Scale Experiment (100 Cases)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  python run_100_case_experiment.py
  python run_100_case_experiment.py --dataset custom.json
  python run_100_case_experiment.py --scenario gold_standard_full
        """
    )
    
    parser.add_argument(
        "--dataset", 
        type=str, 
        default=DEFAULT_DATASET,
        help=f"測試案例 JSON 檔案 (預設: merged_eval_normal.json)"
    )
    
    parser.add_argument(
        "--outdir", 
        type=str, 
        default=None,
        help="輸出目錄 (預設: runs/v31/YYYYMMDD_HHMM)"
    )
    
    parser.add_argument(
        "--scenario", 
        type=str, 
        default="full_scale_100",
        help="場景標籤 (預設: full_scale_100)"
    )
    
    parser.add_argument(
        "--run_id", 
        type=str, 
        default=None,
        help="運行 ID (預設: 自動生成時間戳)"
    )
    
    args = parser.parse_args()
    
    # 設定預設值
    run_id = args.run_id or datetime.now().strftime("%Y%m%d_%H%M")
    output_dir = args.outdir or os.path.join(ROOT_DIR, "runs", "v31", run_id)
    
    # 檢查數據集是否存在
    if not os.path.exists(args.dataset):
        print(f"[ERROR] 數據集不存在: {args.dataset}")
        return 1
    
    # 執行實驗
    return run_experiment(
        dataset_path=args.dataset,
        output_dir=output_dir,
        run_id=run_id,
        scenario=args.scenario
    )


if __name__ == "__main__":
    exit(main())
