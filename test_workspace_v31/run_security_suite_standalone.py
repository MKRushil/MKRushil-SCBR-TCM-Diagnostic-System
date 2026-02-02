#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Security Suite Standalone Runner
獨立安全性測試腳本 - 用於 FSR (FailSafe Rate) 與安全相關指標測試

用法:
    python run_security_suite_standalone.py --outdir <輸出目錄>
"""

import os
import subprocess
import argparse
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)

def main():
    parser = argparse.ArgumentParser(description="獨立安全性測試套件")
    parser.add_argument("--outdir", type=str, default=None, help="輸出目錄")
    parser.add_argument("--dataset", type=str, default=None, help="安全測試案例 JSON 檔案")
    args = parser.parse_args()
    
    # 預設路徑
    run_id = datetime.now().strftime("%Y%m%d_%H%M")
    security_cases = args.dataset or os.path.join(BASE_DIR, "security_test_cases.json")
    out_dir = args.outdir or os.path.join(ROOT_DIR, "runs", "v31", run_id, "security_results")
    
    os.makedirs(out_dir, exist_ok=True)
    
    print(f"{'='*60}")
    print(f"[Security Suite] 獨立安全性測試")
    print(f"{'='*60}")
    print(f"測試案例: {security_cases}")
    print(f"輸出目錄: {out_dir}")
    
    # 準備環境變數
    env = os.environ.copy()
    env["BASELINE_MODE"] = "none"
    env["USE_V31_PIPELINE"] = "true"
    env["PYTHONPATH"] = f"{ROOT_DIR};{os.path.join(ROOT_DIR, 'backend')}"
    
    # 執行安全測試腳本
    security_script = os.path.join(BASE_DIR, "run_security_suite.py")
    
    cmd = [
        "python", security_script,
        "--dataset", security_cases,
        "--outdir", out_dir
    ]
    
    try:
        subprocess.run(cmd, env=env, check=True)
        print(f"\n[SUCCESS] Security Suite 完成")
        print(f"結果已儲存至: {out_dir}")
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Security Suite 失敗: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
