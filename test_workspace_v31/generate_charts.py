import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import seaborn as sns
import os
import argparse
import glob
import json

# Set style
sns.set_theme(style="whitegrid")
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['figure.dpi'] = 300
plt.rcParams['figure.constrained_layout.use'] = True

def load_experiment_data(run_dir):
    """
    Load data from the run directory.
    Expected structure:
    run_dir/
      SCBR-Standard/
         benchmark_cases_*.csv
         benchmark_turns_*.csv
         security_results/security_summary.json
      Baseline-Combined/
         ...
    """
    profiles = ["SCBR-Standard", "Baseline-Combined"]
    data = {}
    
    for p in profiles:
        p_dir = os.path.join(run_dir, p)
        if not os.path.exists(p_dir):
            print(f"Warning: Profile directory not found: {p_dir}")
            continue
            
        # Load Case Metrics
        case_files = glob.glob(os.path.join(p_dir, "benchmark_cases_*.csv"))
        if case_files:
            data[p] = {"cases": pd.read_csv(case_files[0])}
        
        # Load Turn Metrics
        turn_files = glob.glob(os.path.join(p_dir, "benchmark_turns_*.csv"))
        if turn_files:
            if p not in data: data[p] = {}
            data[p]["turns"] = pd.read_csv(turn_files[0])

        # Load Security Data (Only for SCBR-Standard)
        if p == "SCBR-Standard":
            sec_file = os.path.join(p_dir, "security_results", "security_summary.json")
            if os.path.exists(sec_file):
                with open(sec_file, 'r', encoding='utf-8') as f:
                    data[p]["security"] = json.load(f)

    return data

def plot_figure_1_process_quality(data, output_dir):
    """
    Figure 1: Dynamic Process Quality Trajectory
    X: Turn 1-3
    Y: TCRS Score
    Lines: SCBR (Rising) vs Baseline-Combined (Flat/Low)
    """
    print("Generating Figure 1...")
    
    turns_x = [1, 2, 3]
    
    # Process SCBR Data
    scbr_tcrs = []
    if "SCBR-Standard" in data and "turns" in data["SCBR-Standard"]:
        df = data["SCBR-Standard"]["turns"]
        for t in turns_x:
            val = df[df['turn'] == t]['tcrs'].mean()
            scbr_tcrs.append(val if not pd.isna(val) else 0)
    else:
        scbr_tcrs = [0, 0, 0]

    # Process Baseline-Combined Data
    base_tcrs = []
    if "Baseline-Combined" in data and "turns" in data["Baseline-Combined"]:
        df = data["Baseline-Combined"]["turns"]
        for t in turns_x:
            val = df[df['turn'] == t]['tcrs'].mean()
            base_tcrs.append(val if not pd.isna(val) else 0)
    else:
        base_tcrs = [0, 0, 0]

    plt.figure(figsize=(10, 6))
    plt.plot(turns_x, scbr_tcrs, marker='o', linewidth=2.5, label='SCBR-Standard (Spiral)', color='#1f77b4')
    plt.plot(turns_x, base_tcrs, marker='s', linewidth=2.5, linestyle='--', label='Baseline-Combined (Simple RAG)', color='#ff7f0e')

    plt.title('Figure 1: Process Quality Trajectory (TCRS)', fontsize=14, pad=20)
    plt.xlabel('Dialogue Turns (t)', fontsize=12)
    plt.ylabel('TCRS Score (0-1)', fontsize=12)
    plt.ylim(0, 1.05)
    plt.xticks(turns_x, ['Turn 1', 'Turn 2', 'Turn 3'])
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.7)
    
    plt.savefig(os.path.join(output_dir, "Figure_1_Process_Quality.png"))

def plot_figure_2_ambiguity_reduction(data, output_dir):
    """
    Figure 2: Ambiguity Reduction (ARR)
    X: Turn 1-3
    Y: Remaining Ambiguity (Ratio 1.0 -> 0.0)
    """
    print("Generating Figure 2...")
    
    turns_x = [1, 2, 3]
    scbr_arr = []
    base_arr = []
    
    # SCBR
    if "SCBR-Standard" in data and "turns" in data["SCBR-Standard"]:
        df = data["SCBR-Standard"]["turns"]
        for t in turns_x:
            val = df[df['turn'] == t]['ambiguity_ratio'].mean()
            scbr_arr.append(val if not pd.isna(val) else 1.0)
    else:
        scbr_arr = [1.0, 1.0, 1.0]

    # Baseline-Combined
    if "Baseline-Combined" in data and "turns" in data["Baseline-Combined"]:
         df = data["Baseline-Combined"]["turns"]
         for t in turns_x:
            val = df[df['turn'] == t]['ambiguity_ratio'].mean()
            base_arr.append(val if not pd.isna(val) else 1.0)
    else:
        base_arr = [1.0, 1.0, 1.0]

    plt.figure(figsize=(10, 6))
    plt.plot(turns_x, scbr_arr, marker='o', linewidth=2.5, label='SCBR-Standard', color='#1f77b4')
    plt.plot(turns_x, base_arr, marker='s', linewidth=2.5, linestyle='--', label='Baseline-Combined', color='#ff7f0e')

    plt.title('Figure 2: Ambiguity Reduction Efficiency', fontsize=14, pad=20)
    plt.xlabel('Dialogue Turns (t)', fontsize=12)
    plt.ylabel('Remaining Ambiguity Ratio', fontsize=12)
    plt.ylim(-0.05, 1.05)
    plt.xticks(turns_x)
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.7)
    
    plt.savefig(os.path.join(output_dir, "Figure_2_Ambiguity_Reduction.png"))

def plot_figure_3_final_outcome(data, output_dir):
    """
    Figure 3: Final Outcome Comparison (Clustered Bar)
    Metrics: Coverage, A1, RDRR
    """
    print("Generating Figure 3...")
    
    plot_data = []
    profiles = ["SCBR-Standard", "Baseline-Combined"]
    
    for p in profiles:
        if p not in data or "cases" not in data[p]:
            continue
            
        df = data[p]["cases"]
        
        # Coverage
        if 'coverage' in df.columns:
            coverage_score = df['coverage'].mean()
        elif 'tcrs_final' in df.columns:
             coverage_score = df['tcrs_final'].mean()
        else:
             coverage_score = 0
             
        # A1 Semantic
        if 'a1_prime' in df.columns:
            a1_score = df['a1_prime'].mean()
        elif "turns" in data[p]:
            a1_score = data[p]["turns"]['a1_prime'].mean()
        else:
            a1_score = 0
            
        # RDRR
        rdrr_vals = pd.to_numeric(df['rdrr_flag'], errors='coerce')
        rdrr_score = rdrr_vals.mean() 
        if pd.isna(rdrr_score): rdrr_score = 0
        
        plot_data.append({"Profile": p, "Metric": "Coverage", "Score": coverage_score})
        plot_data.append({"Profile": p, "Metric": "A1 (Semantic)", "Score": a1_score})
        plot_data.append({"Profile": p, "Metric": "RDRR (Recovery)", "Score": rdrr_score})
        
    if not plot_data:
        print("Skipping Figure 3: No data for plotting.")
        return
        
    df_plot = pd.DataFrame(plot_data)
    
    plt.figure(figsize=(10, 6))
    sns.barplot(x='Metric', y='Score', hue='Profile', data=df_plot, palette='viridis')
    plt.title('Figure 3: Final Diagnostic Performance', fontsize=14, pad=20)
    plt.ylim(0, 1.05)
    plt.ylabel('Score / Rate', fontsize=12)
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    
    plt.savefig(os.path.join(output_dir, "Figure_3_Final_Outcome.png"))

def plot_figure_8a_security_fsr(data, output_dir):
    """
    Figure 8-A: OWASP Red Teaming Defense (Stacked Bar)
    """
    print("Generating Figure 8-A...")
    
    if "SCBR-Standard" not in data or "security" not in data["SCBR-Standard"]:
        print("Skipping Figure 8-A: No Security Data found for SCBR-Standard.")
        return

    sec_data = data["SCBR-Standard"]["security"]
    
    categories = [d["Category"] for d in sec_data]
    l1 = [d.get("Intercepted", 0) for d in sec_data]
    l2 = [d.get("Mitigated", 0) for d in sec_data]
    failed = [d.get("Failed", 0) for d in sec_data]
    
    df = pd.DataFrame({
        "Category": categories,
        "Intercepted (L1/L2)": l1,
        "Mitigated (System Logic)": l2,
        "FAILED": failed
    })
    
    df.set_index("Category", inplace=True)
    
    colors = ["#2ca02c", "#1f77b4", "#d62728"]
    
    ax = df.plot(kind='barh', stacked=True, color=colors, figsize=(10, 6))
    plt.title('Figure 8-A: Security Defense Layers (OWASP)', fontsize=14, pad=20)
    plt.xlabel('Number of Test Cases', fontsize=12)
    plt.ylabel('Attack Category', fontsize=12)
    plt.legend(title='Defense Strategy', bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    
    plt.savefig(os.path.join(output_dir, "Figure_8A_Security_Defense.png"))

def plot_figure_8b_consistency_ccar(data, output_dir):
    """
    Figure 8-B: Core Medical Logical Consistency (CCAR)
    """
    print("Generating Figure 8-B...")
    
    plot_data = []
    profiles = ["SCBR-Standard", "Baseline-Combined"]
    
    for p in profiles:
        if p not in data or "cases" not in data[p]:
            continue
            
        df = data[p]["cases"]
        ccar_score = df['ccar_flag'].mean()
        plot_data.append({"Profile": p, "Metric": "CCAR", "Score": ccar_score})
    
    if not plot_data:
        print("Skipping Figure 8-B: No data found.")
        return

    df_plot = pd.DataFrame(plot_data)
    
    plt.figure(figsize=(6, 6))
    ax = sns.barplot(x='Profile', y='Score', data=df_plot, palette='magma')
    plt.title('Figure 8-B: Medical Logic Consistency Check', fontsize=14, pad=20)
    plt.ylim(0, 1.1)
    plt.ylabel('CCAR Score (Consistency Rate)', fontsize=12)
    
    for container in ax.containers:
        ax.bar_label(container, fmt='%.2f')

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "Figure_8B_Consistency_CCAR.png"))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_id", required=True, help="Run ID folder name in runs/v31/")
    args = parser.parse_args()
    
    base_run_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "runs", "v31", args.run_id)
    output_charts_dir = os.path.join(base_run_dir, "charts")
    
    if not os.path.exists(base_run_dir):
        print(f"Error: Run directory not found: {base_run_dir}")
        exit(1)
        
    os.makedirs(output_charts_dir, exist_ok=True)
    print(f"Loading data from: {base_run_dir}")
    print(f"Charts will be saved to: {output_charts_dir}")
    
    data = load_experiment_data(base_run_dir)
    
    if not data:
        print("No experimentation data found! Please run 'run_all_experiments.py' first.")
        exit(1)

    plot_figure_1_process_quality(data, output_charts_dir)
    plot_figure_2_ambiguity_reduction(data, output_charts_dir)
    plot_figure_3_final_outcome(data, output_charts_dir)
    plot_figure_8a_security_fsr(data, output_charts_dir)
    plot_figure_8b_consistency_ccar(data, output_charts_dir)
    
    print("\nAll charts generated successfully!")
import pandas as pd
import numpy as np
import seaborn as sns
import os
import argparse
import glob
import json

# Set style
sns.set_theme(style="whitegrid")
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['figure.dpi'] = 300
plt.rcParams['figure.constrained_layout.use'] = True

def load_experiment_data(run_dir):
    """
    Load data from the run directory.
    Expected structure:
    run_dir/
      SCBR-Standard/
         benchmark_cases_*.csv
         benchmark_turns_*.csv
         security_results/security_summary.json
      Baseline-A/
         ...
      Baseline-B/
         ...
    """
    profiles = ["SCBR-Standard", "Baseline-A", "Baseline-B"]
    data = {}
    
    for p in profiles:
        p_dir = os.path.join(run_dir, p)
        if not os.path.exists(p_dir):
            print(f"Warning: Profile directory not found: {p_dir}")
            continue
            
        # Load Case Metrics
        case_files = glob.glob(os.path.join(p_dir, "benchmark_cases_*.csv"))
        if case_files:
            data[p] = {"cases": pd.read_csv(case_files[0])}
        
        # Load Turn Metrics
        turn_files = glob.glob(os.path.join(p_dir, "benchmark_turns_*.csv"))
        if turn_files:
            if p not in data: data[p] = {}
            data[p]["turns"] = pd.read_csv(turn_files[0])

        # Load Security Data (Only for SCBR-Standard)
        if p == "SCBR-Standard":
            sec_file = os.path.join(p_dir, "security_results", "security_summary.json")
            if os.path.exists(sec_file):
                with open(sec_file, 'r', encoding='utf-8') as f:
                    data[p]["security"] = json.load(f)

    return data

def plot_figure_1_process_quality(data, output_dir):
    """
    Figure 1: Dynamic Process Quality Trajectory
    X: Turn 1-3
    Y: TCRS Score
    Lines: SCBR (Rising) vs Static Baseline (Flat)
    """
    print("Generating Figure 1...")
    
    turns_x = [1, 2, 3]
    
    # Process SCBR Data
    scbr_tcrs = []
    if "SCBR-Standard" in data and "turns" in data["SCBR-Standard"]:
        df = data["SCBR-Standard"]["turns"]
        for t in turns_x:
            val = df[df['turn'] == t]['tcrs'].mean()
            scbr_tcrs.append(val if not pd.isna(val) else 0)
    else:
        scbr_tcrs = [0, 0, 0] # Fallback

    # Process Baseline-A (Static) Data
    # Static Baseline usually only has Turn 1. We project it flat.
    static_tcrs_val = 0
    if "Baseline-A" in data and "turns" in data["Baseline-A"]:
        df = data["Baseline-A"]["turns"]
        # Take mean of Turn 1
        val = df[df['turn'] == 1]['tcrs'].mean()
        static_tcrs_val = val if not pd.isna(val) else 0
    
    static_tcrs = [static_tcrs_val] * 3

    plt.figure(figsize=(10, 6))
    plt.plot(turns_x, scbr_tcrs, marker='o', linewidth=2.5, label='SCBR-Standard (Spiral)', color='#1f77b4')
    plt.plot(turns_x, static_tcrs, marker='x', linewidth=2.5, linestyle='--', label='Baseline-A (Static RAG)', color='#ff7f0e')

    # Process Baseline-B (Pure LLM) Data - Also Static
    base_b_tcrs_val = 0
    if "Baseline-B" in data and "turns" in data["Baseline-B"]:
        df = data["Baseline-B"]["turns"]
        val = df[df['turn'] == 1]['tcrs'].mean()
        base_b_tcrs_val = val if not pd.isna(val) else 0
    base_b_tcrs = [base_b_tcrs_val] * 3
    
    plt.plot(turns_x, base_b_tcrs, marker='s', linewidth=2.5, linestyle=':', label='Baseline-B (Pure LLM)', color='#2ca02c')
    
    plt.title('Figure 1: Process Quality Trajectory (TCRS)', fontsize=14, pad=20)
    plt.xlabel('Dialogue Turns (t)', fontsize=12)
    plt.ylabel('TCRS Score (0-1)', fontsize=12)
    plt.ylim(0, 1.05)
    plt.xticks(turns_x, ['Turn 1', 'Turn 2', 'Turn 3'])
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.7)
    
    plt.savefig(os.path.join(output_dir, "Figure_1_Process_Quality.png"))

def plot_figure_2_ambiguity_reduction(data, output_dir):
    """
    Figure 2: Ambiguity Reduction (ARR)
    X: Turn 1-3
    Y: Remaining Ambiguity (Ratio 1.0 -> 0.0)
    """
    print("Generating Figure 2...")
    
    turns_x = [1, 2, 3]
    scbr_arr = []
    
    if "SCBR-Standard" in data and "turns" in data["SCBR-Standard"]:
        df = data["SCBR-Standard"]["turns"]
        for t in turns_x:
            # We want "Remaining Ambiguity Ratio" (ambiguity_ratio col in csv)
            val = df[df['turn'] == t]['ambiguity_ratio'].mean()
            scbr_arr.append(val if not pd.isna(val) else 0)
    else:
        scbr_arr = [1.0, 1.0, 1.0] # Fallback

    # Static Baseline (Assuming no reduction if no interaction, or just flat T1)
    static_arr_val = 1.0
    if "Baseline-A" in data and "turns" in data["Baseline-A"]:
         df = data["Baseline-A"]["turns"]
         val = df[df['turn'] == 1]['ambiguity_ratio'].mean()
         static_arr_val = val if not pd.isna(val) else 1.0
    static_arr = [static_arr_val] * 3

    plt.figure(figsize=(10, 6))
    plt.plot(turns_x, scbr_arr, marker='o', linewidth=2.5, label='SCBR-Standard', color='#1f77b4')
    plt.plot(turns_x, static_arr, marker='x', linewidth=2.5, linestyle='--', label='Baseline-A (Static RAG)', color='#ff7f0e')

    # Baseline-B (Pure LLM) - Also Flat 1.0 (No reduction)
    static_b_arr_val = 1.0
    if "Baseline-B" in data and "turns" in data["Baseline-B"]:
         df = data["Baseline-B"]["turns"]
         val = df[df['turn'] == 1]['ambiguity_ratio'].mean()
         static_b_arr_val = val if not pd.isna(val) else 1.0
    static_b_arr = [static_b_arr_val] * 3
    
    plt.plot(turns_x, static_b_arr, marker='s', linewidth=2.5, linestyle=':', label='Baseline-B (Pure LLM)', color='#2ca02c')
    
    plt.title('Figure 2: Ambiguity Reduction Efficiency', fontsize=14, pad=20)
    plt.xlabel('Dialogue Turns (t)', fontsize=12)
    plt.ylabel('Remaining Ambiguity Ratio', fontsize=12)
    plt.ylim(-0.05, 1.05)
    plt.xticks(turns_x)
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.7)
    
    plt.savefig(os.path.join(output_dir, "Figure_2_Ambiguity_Reduction.png"))

def plot_figure_3_final_outcome(data, output_dir):
    """
    Figure 3: Final Outcome Comparison (Clustered Bar)
    Metrics: Coverage, A1, RDRR
    Groups: SCBR, Baseline-A, Baseline-B
    """
    print("Generating Figure 3...")
    
    metrics = ['M7_Coverage', 'M6_A1_Prime', 'M5_RDRR'] # CSV keys might differ, let's map
    metrics = ['M6_Coverage', 'M5_A1_Prime', 'M4_RDRR'] # Updated per V3.1 specs
    display_metrics = ['Coverage (M6)', 'A1 Semantic (M5)', 'RDRR (M4)']
    
    # Prepare Data
    plot_data = []
    profiles = ["SCBR-Standard", "Baseline-A", "Baseline-B"]
    
    for p in profiles:
        if p not in data or "cases" not in data[p]:
            continue
            
        df = data[p]["cases"]
        
        # M7 Coverage (Need to implementation in run_benchmark.py or proxy?)
        # 12.md: Coverage (證型覆蓋率). Currently run_benchmark doesn't output "coverage".
        # We will use "tcrs_final" as proxy or 0 if missing for now, 
        # BUT run_benchmark DOES output 'tcrs_final', 'rdrr_flag', etc.
        # Let's verify run_benchmark output schema (step 775)
        # It has "tcrs_final", "slope", "tts", "arr", "rahr", "rdrr_flag", "failsafe_match", "ccar_flag", "her_flag".
        # It DOES NOT have Coverage explicit. 
        # We will use F1-Score proxy from TCRS? Or maybe TCRS IS Coverage?
        # TCRS = 0.5 * (Diagnosis_Hit + Symptom_Coverage).
        # Let's use 'tcrs_final' for Coverage proxy for now, 
        # OR calculate A1 from turns?
        # run_benchmark outputs 'tcrs_t3'.
        
        # 12.md definition:
        # Coverage: 證型覆蓋率 (M7_Coverage). Now exported in CSV.
        if 'coverage' in df.columns:
            coverage_score = df['coverage'].mean()
        elif 'tcrs_final' in df.columns:
             # Fallback for old data
             coverage_score = df['tcrs_final'].mean()
        else:
             coverage_score = 0
             
        # A1: Soft semantic similarity (M6_A1_Prime). Now exported in CSV.
        if 'a1_prime' in df.columns:
            a1_score = df['a1_prime'].mean()
        elif "turns" in data[p]:
            # Fallback to Turns CSV if Case CSV missing it
            a1_score = data[p]["turns"]['a1_prime'].mean()
        else:
            a1_score = 0
            
        # RDRR: Retrieval Do-Over Recovery Rate.
        # run_benchmark: column "rdrr_flag" (1 or 0).
        # Only relevant for Degraded scenarios?
        # But Figure 3 in 12.md shows it for all.
        # If NA, treat as 0 or exclude.
        rdrr_vals = pd.to_numeric(df['rdrr_flag'], errors='coerce')
        rdrr_score = rdrr_vals.mean() 
        if pd.isna(rdrr_score): rdrr_score = 0
        
        plot_data.append({"Profile": p, "Metric": "Coverage", "Score": coverage_score})
        plot_data.append({"Profile": p, "Metric": "A1 (Semantic)", "Score": a1_score})
        plot_data.append({"Profile": p, "Metric": "RDRR (Recovery)", "Score": rdrr_score})
        
    df_plot = pd.DataFrame(plot_data)
    
    plt.figure(figsize=(10, 6))
    sns.barplot(x='Metric', y='Score', hue='Profile', data=df_plot, palette='viridis')
    plt.title('Figure 3: Final Diagnostic Performance', fontsize=14, pad=20)
    plt.ylim(0, 1.05)
    plt.ylabel('Score / Rate', fontsize=12)
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    
    plt.savefig(os.path.join(output_dir, "Figure_3_Final_Outcome.png"))

def plot_figure_8a_security_fsr(data, output_dir):
    """
    Figure 8-A: OWASP Red Teaming Defense (Stacked Bar)
    L1 (Blocked) vs L2 (Refusal) vs Failed
    """
    print("Generating Figure 8-A...")
    
    if "SCBR-Standard" not in data or "security" not in data["SCBR-Standard"]:
        print("Skipping Figure 8-A: No Security Data found for SCBR-Standard.")
        return

    sec_data = data["SCBR-Standard"]["security"]
    sec_data = data["SCBR-Standard"]["security"]
    # sec_data is list of dicts: {"Category":..., "Intercepted":..., "Mitigated":..., "Failed":..., "Total":...}
    
    categories = [d["Category"] for d in sec_data]
    l1 = [d.get("Intercepted", 0) for d in sec_data] # Use .get for safety
    l2 = [d.get("Mitigated", 0) for d in sec_data]
    failed = [d.get("Failed", 0) for d in sec_data]
    
    # Create DataFrame for plotting
    df = pd.DataFrame({
        "Category": categories,
        "Intercepted (L1/L2)": l1,
        "Mitigated (System Logic)": l2,
        "FAILED": failed
    })
    
    df.set_index("Category", inplace=True)
    
    # Colors
    # Colors
    colors = ["#2ca02c", "#1f77b4", "#d62728"] # Green (Intercepted), Blue (Mitigated), Red (Fail)
    
    ax = df.plot(kind='barh', stacked=True, color=colors, figsize=(10, 6))
    plt.title('Figure 8-A: Security Defense Layers (OWASP)', fontsize=14, pad=20)
    plt.xlabel('Number of Test Cases', fontsize=12)
    plt.ylabel('Attack Category', fontsize=12)
    plt.legend(title='Defense Strategy', bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    
    plt.savefig(os.path.join(output_dir, "Figure_8A_Security_Defense.png"))

def plot_figure_8b_consistency_ccar(data, output_dir):
    """
    Figure 8-B: Core Medical Logical Consistency (CCAR)
    Bar Chart: SCBR vs Pure LLM
    """
    print("Generating Figure 8-B...")
    
    plot_data = []
    profiles = ["SCBR-Standard", "Baseline-A", "Baseline-B"] # Include all 3 groups
    
    for p in profiles:
        if p not in data or "cases" not in data[p]:
            continue
            
        df = data[p]["cases"]
        # run_benchmark: "ccar_flag" column (1 or 0)
        ccar_score = df['ccar_flag'].mean()
        
        plot_data.append({"Profile": p, "Metric": "CCAR", "Score": ccar_score})
    
    if not plot_data:
        print("Skipping Figure 8-B: No data found.")
        return

    df_plot = pd.DataFrame(plot_data)
    
    plt.figure(figsize=(6, 6))
    ax = sns.barplot(x='Profile', y='Score', data=df_plot, palette='magma')
    plt.title('Figure 8-B: Medical Logic Consistency Check', fontsize=14, pad=20)
    plt.ylim(0, 1.1)
    plt.ylabel('CCAR Score (Consistency Rate)', fontsize=12)
    
    for container in ax.containers:
        ax.bar_label(container, fmt='%.2f')

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "Figure_8B_Consistency_CCAR.png"))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_id", required=True, help="Run ID folder name in runs/v31/")
    args = parser.parse_args()
    
    # Define paths
    base_run_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "runs", "v31", args.run_id)
    output_charts_dir = os.path.join(base_run_dir, "charts")
    
    if not os.path.exists(base_run_dir):
        print(f"Error: Run directory not found: {base_run_dir}")
        exit(1)
        
    os.makedirs(output_charts_dir, exist_ok=True)
    print(f"Loading data from: {base_run_dir}")
    print(f"Charts will be saved to: {output_charts_dir}")
    
    # Load Data
    data = load_experiment_data(base_run_dir)
    
    if not data:
        print("No experimentation data found! Please run 'run_all_experiments.py' first.")
        exit(1)

    # Generate Charts
    plot_figure_1_process_quality(data, output_charts_dir)
    plot_figure_2_ambiguity_reduction(data, output_charts_dir)
    plot_figure_3_final_outcome(data, output_charts_dir)
    plot_figure_8a_security_fsr(data, output_charts_dir)
    plot_figure_8b_consistency_ccar(data, output_charts_dir)
    
    print("\nAll charts generated successfully!")