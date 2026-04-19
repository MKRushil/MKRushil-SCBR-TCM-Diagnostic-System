import os
import subprocess
import time
from datetime import datetime

# 配置內部路徑
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASETS = [
    {"path": os.path.join(BASE_DIR, "merged_eval_normal.json"), "scenario": "full_scale_100"},
]
RUN_ID = datetime.now().strftime("%Y%m%d_%H%M")
OUT_DIR = os.path.join(os.path.dirname(BASE_DIR), "runs", "v31", RUN_ID)

EXPERIMENTS = [
    # SCBR-Standard 已完成，註解掉
    # {
    #     "name": "SCBR-Standard",
    #     "env": {"BASELINE_MODE": "none", "USE_V31_PIPELINE": "true"},
    #     "desc": "實驗組: 螺旋協商四步驟 (Full Spiral SCBR)"
    # },
    {
        "name": "Baseline-Combined",
        "env": {"BASELINE_MODE": "simple_rag", "USE_V31_PIPELINE": "true"},
        "desc": "對照組: 多回合靜態檢索 (Multi-turn RAG, No Critic)"
    }
]

def run_experiment(exp):
    print(f"\n{'='*60}")
    print(f"[Experiment] 啟動實驗: {exp['name']} ({exp['desc']})")
    print(f"{'='*60}")
    
    # 準備環境變數
    env = os.environ.copy()
    env.update(exp['env'])
    
    # 確保 PYTHONPATH 包含根目錄與 backend，以便 run_benchmark.py 能正確載入
    ROOT_DIR = os.path.dirname(BASE_DIR)
    env["PYTHONPATH"] = f"{ROOT_DIR};{os.path.join(ROOT_DIR, 'backend')}"
    
    benchmark_script = os.path.join(BASE_DIR, "run_benchmark.py")
    
    for ds in DATASETS:
        print(f"\n跑測資料集: {os.path.basename(ds['path'])} (場景: {ds['scenario']})")
        
        cmd = [
            "python", benchmark_script,
            "--dataset", ds['path'],
            "--outdir", OUT_DIR,
            "--profile", exp['name'],
            "--run_id", RUN_ID,
            "--scenario", ds['scenario']
        ]
        
        try:
            subprocess.run(cmd, env=env, check=True)
            print(f"[SUCCESS] {exp['name']} - {ds['scenario']} 完成")
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] {exp['name']} - {ds['scenario']} 失敗: {e}")

    # NOTE: Security Suite 已移至獨立腳本 run_security_suite_standalone.py

if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"工作目錄: {BASE_DIR}")
    print(f"實驗結果將儲存在: {OUT_DIR}")
    
    start_time = time.time()
    
    for exp in EXPERIMENTS:
        run_experiment(exp)
        
    duration = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"所有實驗已跑完！總耗時: {duration/60:.1f} 分鐘")
    print(f"請至 {OUT_DIR} 提取 CSV 數據進行分析。")
    print(f"{'='*60}")
