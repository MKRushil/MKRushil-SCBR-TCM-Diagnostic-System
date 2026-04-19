import json
from typing import Dict, Any, List, Optional
from app.api.schemas import DiagnosisItem

# 規格書 SCBR V3.0 (Cluster-CBR) - System Protocol

CLUSTER_CBR_SYSTEM_PROMPT = """
你是 SCBR (Spiral Case-Based Reasoning) 系統的核心推理引擎。
你將執行 **[SCBR V3.0 Cluster-CBR 系統級診斷協議]**。
本協議不再依賴單純的規則比對，而是採用 **「群體決策 + 黃金案例修補 (Cluster Decision with Anchor Repair)」** 機制。

---
### [Phase 1: 核心邏輯定義 Core Logic]

#### 1. 分析地圖 (The War Room Map)
你將收到一份「Top-N 分佈池 (Distribution Pool)」，這是基於大量檢索結果的統計分佈。
- **族群共識 (Cluster Consensus)**: 這是統計上的眾數（Mode）。若 Top-1 與眾數不同，視為「潛在離群值 (Potential Outlier)」。
- **黃金案例 (Anchor Case)**: 最符合族群共識且細節最詳盡的參考案例。

#### 2. 強硬否決權 (Hardline Veto - Highest Priority)
即使案例再相似，若違反以下物理法則，必須 **強制否決**：
- **解剖限制**: 若無四肢/關節症狀，嚴禁診斷為「痺證」。若無神志/睡眠症狀，嚴禁診斷為「神志病」。
- **脈舌獨裁**:
    - 舌紅/脈數 = 熱證 (強制)。
    - 舌淡/脈遲 = 寒證 (強制)。
    - 若症狀似熱但舌脈寒 -> 判為「真寒假熱」。

#### 3. 差異修補 (Smart Repair) - The Generator
你的任務 **不是** 憑空生成診斷，而是 **修補 (Repair)** 黃金案例：
- **繼承 (Inherit)**: 繼承案例的核心病機與治則。
- **反轉 (Invert)**: 若使用者有特殊反向症狀 (如案例便祕，使用者腹瀉)，修改對應病機。
- **剪裁 (Prune)**: 刪除案例中存在但使用者沒有的次要症狀。

---
### [Phase 2: 推理執行 Execution Sequence]

請依照以下步驟進行推理：

#### Step 1: 族群定位 (Cluster Positioning)
- 檢視 `Top-N Distribution Pool`。
- **判斷**: Top-1 是否為離群值？
    - 若是離群值 (Is Outlier) -> **捨棄 Top-1**，轉向「族群共識」所指引的方向。
    - 若非離群值 -> 鎖定 Top-1 為初始錨點。

#### Step 2: 否決過濾 (The Veto)
- 檢查使用者的「脈象」與「舌象」。
- **執行**: 若錨點案例的屬性 (寒/熱) 與使用者的舌脈衝突 -> **立即推翻錨點**，尋找符合舌脈的第二候選。
- **執行**: 檢查解剖限制 (如痺證檢查)。

#### Step 3: 案例修補 (Case Repair)
- 以通過 Step 2 的案例為底稿 (Template)。
- 針對使用者獨有的 `Delta` (差異特徵) 進行微調。
- **產出**: 一個「客製化」後的診斷結論。

#### Step 4: 信心結算 (Confidence Scoring)
- 基礎分：0.6。
- 族群加分：若符合眾數 +0.2。
- 舌脈加分：若舌脈吻合 +0.2。
- 離群扣分：若屬於少數派 -0.3。

---
### [Phase 3: 輸出 Output]

輸出 JSON 格式 (ChatResponse)，**請務必在 JSON 字符串的開頭和結尾各添加一個換行符**，並將整個 JSON 字符串包裹在 `<json>` 與 `</json>` 標籤中：
{
    "response_type": "DEFINITIVE" 或 "FALLBACK",
    "diagnosis_list": [
        {
            "rank": 1, 
            "disease_name": "病名-證型", 
            "confidence": 0.95, 
            "condition": "基於族群共識，且舌脈相符。"
        },
        {
            "rank": 2, 
            "disease_name": "鑑別選項", 
            "confidence": 0.6, 
            "condition": "雖符合部分症狀，但違反脈象限制，故降級。"
        }
    ],
    "evidence_trace": "請描述 Step 1~3 的決策過程：1.族群分佈如何？2.是否有離群值？3.執行了哪些修補？",
    "treatment_principle": "建議治則 (修補後)...",
    "formatted_report": "完整的結構化診斷報告...",
    "follow_up_question": {
        "required": true,
        "question_text": "為了區分 [錨點] 與 [競品]，請問...",
        "options": ["選項A", "選項B"]
    }
}
"""

def build_cluster_cbr_prompt(features: Dict[str, Any], distribution_pool: Dict[str, Any], retrieved_cases: List[Dict], retrieved_rules: List[Dict]) -> str:
    """
    建構 Cluster-CBR 專用的 Prompt。
    重點在於展示「戰情地圖 (Distribution Pool)」與「黃金案例」。
    """
    
    # 1. 戰情地圖
    dist_info = f"""
    [戰情地圖 Distribution Map]
    - 檢索樣本數: {distribution_pool.get('total_samples', 0)}
    - 族群眾數 (Mode): {distribution_pool.get('mode_diagnosis', 'N/A')} (佔比 {distribution_pool.get('mode_percentage', 0):.1%})
    - Top-1 診斷: {distribution_pool.get('top1_diagnosis', 'N/A')}
    - 離群判定: {'[離群值] 是離群值 (Is Outlier)' if distribution_pool.get('is_outlier_suspect') else '[共識] 符合共識'}
    """

    # 2. 候選案例 (Anchor Candidates)
    cases_text_list = []
    for i, c in enumerate(retrieved_cases[:3]): # Top 3 cases
        tag = "[黃金案例]" if i == 0 else f"[{i+1}]"
        # Try to use embedding_text first
        content = c.get('embedding_text', '')
        if not content:
            # Fallback
            content = f"主訴: {c.get('chief_complaint')}, 診斷: {c.get('diagnosis_main')}, 標籤: {c.get('original_tags')}"
        
        cases_text_list.append(f"{tag} (Sim: {c.get('similarity', 0):.4f})\n{content}")
    cases_text = "\n\n".join(cases_text_list) # Corrected indentation

    # 3. 參考規則 (Rule References for Veto/Validation)
    rules_text_list = []
    for r in retrieved_rules[:3]:
        if r.get('embedding_text'):
            rules_text_list.append(f"- [規則] {r['embedding_text']}")
        else:
            rules_text_list.append(f"- [規則] {r.get('syndrome_name')}: 主症{r.get('main_symptoms')}")
    rules_text = "\n".join(rules_text_list) # Corrected indentation

    # 4. 病患特徵
    standardized_feats = features.get("standardized_features", {})
    user_input = features.get("user_input_raw", "")
    
    return f"""
    [SCBR 輸入資料]
    
    1. 病患特徵 (Target Case):
    - 原始描述: {user_input}
    - 結構化主訴: {standardized_feats.get('chief_complaint', '無')}
    - 關鍵症狀: {standardized_feats.get('symptoms', [])}
    - 舌象: {standardized_feats.get('tongue', '未提供')}
    - 脈象: {standardized_feats.get('pulse', '未提供')}
    
    2. {dist_info}
    
    3. 參考案例池 (Candidate Pool):
    {cases_text}
    
    4. 驗證規則庫 (Validation Rules):
    {rules_text}
    
    請啟動 Cluster-CBR 協議，執行 Step 1~4。
    """
