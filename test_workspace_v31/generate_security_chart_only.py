
import json
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import os
import argparse
import sys

# 設定繁體中文字型 (Windows 適用)
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'SimHei', 'Arial']
plt.rcParams['axes.unicode_minus'] = False

def generate_chart(json_path, output_path):
    print(f"Reading data from: {json_path}")
    
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            summary_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: File not found at {json_path}")
        # 如果找不到檔案，生成範例資料供測試
        print("Generating mock data for demonstration...")
        summary_data = [
            {"Category": "Direct Prompt Injection", "Intercepted": 10, "Mitigated": 12, "Failed": 3, "Total": 25},
            {"Category": "Indirect Prompt Injection", "Intercepted": 8, "Mitigated": 14, "Failed": 3, "Total": 25},
            {"Category": "System Prompt Leakage", "Intercepted": 15, "Mitigated": 10, "Failed": 0, "Total": 25},
            {"Category": "Jailbreak Variants", "Intercepted": 5, "Mitigated": 15, "Failed": 5, "Total": 25}
        ]

    # 準備繪圖資料
    chart_layers = ["Intercepted", "Mitigated", "Failed"]
    # 對應中文標籤 (如果 JSON key 是英文，這邊做 Mapping；如果 JSON 已經是中文則直接用)
    # 假設 JSON 還是英文 Key，但我們想顯示中文圖例
    
    # 檢查 JSON 資料結構
    first_item = summary_data[0] if summary_data else {}
    print(f"Data sample: {first_item}")
    
    chart_data = []
    
    # 定義圖層順序與顏色
    layers_order = ["Intercepted", "Mitigated", "Failed"]
    colors_map = {
        "Intercepted": "#2ca02c", # Green (攔截成功)
        "Mitigated": "#1f77b4",   # Blue (緩解成功)
        "Failed": "#d9534f"       # Red (防禦失敗)
    }
    
    # 處理資料轉為 Long Format
    for item in summary_data:
        cat = item.get("Category", "Unknown")
        
        # 嘗試讀取不同可能的 Key (相容英文與中文 Key)
        val_intercepted = item.get("Intercepted") or item.get("Intercepted (L1/L2)") or item.get("防禦成功") or 0
        val_mitigated = item.get("Mitigated") or item.get("Mitigated (System Logic)") or item.get("緩解成功") or 0
        val_failed = item.get("Failed") or item.get("FAILED") or item.get("防禦失敗") or 0
        
        chart_data.append({"Category": cat, "Layer": "Intercepted", "Count": val_intercepted})
        chart_data.append({"Category": cat, "Layer": "Mitigated", "Count": val_mitigated})
        chart_data.append({"Category": cat, "Layer": "Failed", "Count": val_failed})

    df = pd.DataFrame(chart_data)
    
    # 建立 Pivot Table
    df_pivot = df.pivot(index='Category', columns='Layer', values='Count')
    # 確保順序
    df_pivot = df_pivot.reindex(columns=layers_order).fillna(0)
    
    # 繪圖
    plt.figure(figsize=(12, 6))
    sns.set_theme(style="whitegrid")
    
    # 重新設定字型 (因為 seaborn set_theme 可能會重置字型)
    plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'SimHei', 'Arial']
    plt.rcParams['axes.unicode_minus'] = False
    
    ax = df_pivot.plot(
        kind='barh', 
        stacked=True, 
        color=[colors_map[col] for col in df_pivot.columns], 
        figsize=(12, 6), 
        width=0.7
    )
    
    plt.title('Security Defense Layer Analysis', fontsize=15, pad=20)
    plt.xlabel('Number of Test Cases', fontsize=12) 
    plt.ylabel('Attack Category', fontsize=12)
    
    # 設定中文圖例
    handles, labels = ax.get_legend_handles_labels()
    zh_labels = ["攔截成功", "緩解成功", "防禦失敗"]
    plt.legend(handles, zh_labels, title='防禦機制', bbox_to_anchor=(1.0, 1), loc='upper left')
    
    plt.tight_layout()
    
    # 儲存
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Chart saved to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Security Chart Standalone")
    parser.add_argument("--input", default="tests/security_summary.json", help="Path to security_summary.json")
    parser.add_argument("--output", default="security_defense_chart_standalone.png", help="Output image path")
    
    args = parser.parse_args()
    
    # 自動尋找檔案
    input_path = args.input
    if not os.path.exists(input_path):
        # 嘗試在常見位置尋找
        candidates = [
            "security_summary.json",
            "tests/security_summary.json",
            "../tests/security_summary.json",
            "c:/work/系統-中醫/tcm-scbr-agent/tests/security_summary.json"
        ]
        for c in candidates:
            if os.path.exists(c):
                input_path = c
                break
    
    generate_chart(input_path, args.output)
