import os
import re
import matplotlib.pyplot as plt
import numpy as np
import textwrap

# Setup paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHART_DIR = os.path.join(BASE_DIR, "chart")
os.makedirs(CHART_DIR, exist_ok=True)

# File paths
SCBR_REPORT = os.path.join(os.path.dirname(BASE_DIR), "runs", "v31", "20260131_0620", "SCBR-Standard", "benchmark_report_SCBR-Standard_20260131_0620.md")
BASELINE_REPORT = os.path.join(os.path.dirname(BASE_DIR), "runs", "v31", "20260201_0158", "Baseline-Combined", "benchmark_report_Baseline-Combined_20260201_0158.md")

def parse_report(file_path):
    data = {"turns_tcrs": {}, "metrics": {}}
    if not os.path.exists(file_path):
        print(f"Warning: File not found: {file_path}")
        return data
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    turn_matches = re.findall(r"\|\s*(\d+)\s*\|\s*([\d\.]+)\s*\|", content)
    for turn, tcrs in turn_matches:
        data["turns_tcrs"][int(turn)] = float(tcrs)
    metric_matches = re.findall(r"\|\s*([^\|\s]+)\s*\|\s*\.\.\.\s*\|\s*([\d\.\-N/A]+)\s*\|", content)
    for m_id, val in metric_matches:
        try:
            data["metrics"][m_id] = float(val)
        except ValueError:
            data["metrics"][m_id] = 0.0
    return data

scbr_data = parse_report(SCBR_REPORT)
base_data = parse_report(BASELINE_REPORT)

plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.size'] = 12
plt.rcParams['axes.titlesize'] = 14
plt.rcParams['axes.labelsize'] = 12
COLORS = {'SCBR': '#2E75B6', 'Baseline': '#ED7D31'}

def save_plot(fig, filename):
    path = os.path.join(CHART_DIR, filename)
    fig.savefig(path, dpi=300, bbox_inches='tight')
    print(f"Saved {path}")
    plt.close(fig)

def format_value(v):
    return f"{v:.2f}" if abs(v) > 0.001 else "0.00"

def add_value_labels(ax, rects):
    """Attach a text label above each bar in *rects*, displaying its height."""
    for rect in rects:
        height = rect.get_height()
        # Handle negative values for placement
        y_pos = height if height >= 0 else 0
        va = 'bottom' if height >= 0 else 'top'
        
        ax.text(rect.get_x() + rect.get_width()/2., y_pos + (0.01 if height >=0 else -0.02),
                format_value(height),
                ha='center', va=va, fontsize=10, fontweight='bold', color='black')

def wrap_labels(labels, width=15):
    return ['\n'.join(textwrap.wrap(l, width)) for l in labels]

# Figure 1: Process Trajectory (Line Chart)
def plot_figure_1():
    fig, ax = plt.subplots(figsize=(8, 5))
    turns = [1, 2, 3]
    scbr_tcrs = [scbr_data["turns_tcrs"].get(t, 0) for t in turns]
    base_tcrs = [base_data["turns_tcrs"].get(t, 0) for t in turns]
    
    ax.plot(turns, scbr_tcrs, marker='o', markersize=8, label='SCBR-Standard', color=COLORS['SCBR'], linewidth=2.5)
    ax.plot(turns, base_tcrs, marker='s', markersize=8, label='Baseline-Combined', color=COLORS['Baseline'], linewidth=2.5, linestyle='--')
    
    ax.set_title("Process Trajectory\n(TCRS Score Evolution)", pad=15)
    ax.set_ylabel("TCRS Score")
    ax.set_xlabel("Dialogue Turns")
    ax.set_xticks(turns)
    ax.set_xticklabels([f"Turn {t}" for t in turns])
    
    # Auto Scale Y
    all_vals = scbr_tcrs + base_tcrs
    if all_vals:
        ax.set_ylim(min(all_vals)-0.05, max(all_vals)+0.05)
    
    ax.legend()
    ax.grid(True, linestyle=':', alpha=0.6)
    
    # Annotate
    for i, v in enumerate(scbr_tcrs):
        ax.annotate(f"{v:.2f}", (turns[i], v), xytext=(0, 8), textcoords='offset points', ha='center', color=COLORS['SCBR'], fontweight='bold', fontsize=10)
    for i, v in enumerate(base_tcrs):
        ax.annotate(f"{v:.2f}", (turns[i], v), xytext=(0, -15), textcoords='offset points', ha='center', color=COLORS['Baseline'], fontweight='bold', fontsize=10)
        
    save_plot(fig, "figure1_process_trajectory.png")

# Figure 2: Convergence Trend (Vertical Bar)
def plot_figure_2():
    """
    Figure 2: Convergence Trend (Vertical Bar)
    - Vertical bar chart
    - Fixed decimal display (4 digits)
    - Compact layout for 2 bars
    - Academic-safe y-axis scaling
    """

    # ===== 1. Figure size (關鍵：避免下方留白) =====
    fig, ax = plt.subplots(figsize=(3.5, 3.2))

    # ===== 2. Data =====
    groups = ["SCBR-Standard", "Baseline-Combined"]
    groups_wrapped = wrap_labels(groups, 10)

    slopes = [
        scbr_data["metrics"].get("M1_Slope", 0.0),
        base_data["metrics"].get("M1_Slope", 0.0)
    ]

    # ===== 3. Bars =====
    rects = ax.bar(
        groups_wrapped,
        slopes,
        width=0.6,
        color=[COLORS["SCBR"], COLORS["Baseline"]]
    )

    # ===== 4. Titles & labels =====
    ax.set_title("Convergence Trend\n(Slope)", pad=10)
    ax.set_ylabel("Slope Value (ΔScore / Turn)")

    # Zero reference line (必要，學術合理)
    ax.axhline(0, color="black", linewidth=0.8)

    # ===== 5. Y-axis range (避免視覺留白) =====
    min_y = min(slopes)
    pad = abs(min_y) * 0.25 if min_y != 0 else 0.0003
    ax.set_ylim(min_y - pad, pad * 0.4)

    # ===== 6. Value labels (固定顯示 4 位小數) =====
    for rect in rects:
        value = rect.get_height()
        offset = abs(value) * 0.08

        ax.text(
            rect.get_x() + rect.get_width() / 2,
            value - offset if value < 0 else value + offset,
            f"{value:.4f}",          # ← -0.0007 / -0.0011
            ha="center",
            va="top" if value < 0 else "bottom",
            fontsize=9
        )

    # ===== 7. Layout control (比 tight_layout 穩定) =====
    plt.subplots_adjust(top=0.85, bottom=0.18)

    # ===== 8. Save =====
    save_plot(fig, "figure2_convergence_trend.png")


# Figure 3: Final Diagnostic Performance (Vertical Grouped Bar)
def plot_figure_3():
    fig, ax = plt.subplots(figsize=(8, 5))
    
    metrics = ['A1 Score (Semantic)', 'Coverage (Keyword)']
    metrics_wrapped = wrap_labels(metrics, 12)
    x = np.arange(len(metrics))
    width = 0.35
    
    scbr_vals = [
        scbr_data["metrics"].get("M6_A1'", 0),
        scbr_data["metrics"].get("M7_Coverage", 0)
    ]
    base_vals = [
        base_data["metrics"].get("M6_A1'", 0),
        base_data["metrics"].get("M7_Coverage", 0)
    ]
    
    rects1 = ax.bar(x - width/2, scbr_vals, width, label='SCBR-Standard', color=COLORS['SCBR'])
    rects2 = ax.bar(x + width/2, base_vals, width, label='Baseline-Combined', color=COLORS['Baseline'])
    
    ax.set_title("Final Diagnostic Performance", pad=15)
    ax.set_ylabel("Performance Score")
    ax.set_xticks(x)
    ax.set_xticklabels(metrics_wrapped)
    ax.set_ylim(0, 1.0)

    # ✅ 1) legend 移到圖外，避免擋到數值標籤
    ax.legend(
        loc='center left',
        bbox_to_anchor=(1.02, 0.15),   # 右側、偏下（也可改 0.5 置中）
        title="Configuration",
        frameon=True
    )

    # ✅ 2) 數值標籤：固定往上偏移一點，避免貼到 bar 頂
    def add_value_labels_with_offset(ax, rects, fmt="{:.2f}", offset=0.02):
        for rect in rects:
            h = rect.get_height()
            ax.text(
                rect.get_x() + rect.get_width() / 2,
                h + offset,
                fmt.format(h),
                ha="center",
                va="bottom",
                fontsize=12,
                fontweight="bold",
                clip_on=False  # 避免貼近邊界時被裁切
            )

    add_value_labels_with_offset(ax, rects1, fmt="{:.2f}", offset=0.02)
    add_value_labels_with_offset(ax, rects2, fmt="{:.2f}", offset=0.02)

    # ✅ 3) 右邊要留空間給 legend（關鍵）
    plt.subplots_adjust(right=0.78)

    save_plot(fig, "figure3_final_performance.png")


# Figure 4A: Convergence Efficiency (TTS) - Vertical
def plot_figure_4A():
    fig, ax = plt.subplots(figsize=(6, 5))
    
    groups = ['SCBR-Standard', 'Baseline-Combined']
    groups_wrapped = wrap_labels(groups, 10)
    tts_vals = [scbr_data["metrics"].get("M2_TTS'", 0), base_data["metrics"].get("M2_TTS'", 0)]
    
    rects = ax.bar(groups_wrapped, tts_vals, color=[COLORS['SCBR'], COLORS['Baseline']], width=0.5)
    
    ax.set_title("Convergence Efficiency (TTS)", pad=15)
    ax.set_ylabel("Turns to Stabilize")
    
    # Scale Y to have headroom
    ax.set_ylim(0, max(tts_vals) * 1.2)
    
    add_value_labels(ax, rects)
    
    save_plot(fig, "figure4a_efficiency_tts.png")

# Figure 4B: Medical Consistency (CCAR) - Vertical
def plot_figure_4B():
    fig, ax = plt.subplots(figsize=(6, 5))
    
    groups = ['SCBR-Standard', 'Baseline-Combined']
    groups_wrapped = wrap_labels(groups, 10)
    ccar_vals = [scbr_data["metrics"].get("M9_CCAR", 0), base_data["metrics"].get("M9_CCAR", 0)]
    
    rects = ax.bar(groups_wrapped, ccar_vals, color=[COLORS['SCBR'], COLORS['Baseline']], width=0.5)
    
    ax.set_title(" Medical Consistency (CCAR)", pad=15)
    ax.set_ylabel("Consistency Ratio")
    
    ax.set_ylim(0, 1.15) # Max 1.0
    
    add_value_labels(ax, rects)
    
    save_plot(fig, "figure4b_consistency_ccar.png")

if __name__ == "__main__":
    plot_figure_1()
    plot_figure_2()
    plot_figure_3()
    plot_figure_4A()
    plot_figure_4B()
