# backend/app/core/pss.py
"""
Provisional Syndrome State (PSS) - V3.1 核心狀態管理模組

定義：
- ProvisionalSyndromeState Schema
- StageDecider 邏輯
- PSSBuilder 信心計算
- Anchor Gating 驗證
- Stability 層級距離計算
"""

from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel
from enum import Enum

# === REQUIRED KEYS BY CLUSTER (用於 Coverage 計算) ===
REQUIRED_KEYS_BY_CLUSTER = {
    "肺系_外感": ["tongue", "pulse", "cold_heat", "sweating", "sore_throat"],
    "肺系_咳嗽": ["tongue", "pulse", "cold_heat", "phlegm_color", "cough_timing"],
    "肺系_喘證": ["tongue", "pulse", "cold_heat", "dyspnea_type", "activity_tolerance"],
    "脾胃_內傷": ["tongue", "pulse", "appetite", "stool", "abdominal_pain"],
    "脾胃_嘔吐": ["tongue", "pulse", "vomit_content", "nausea_timing", "appetite"],
    "心系_心悸": ["tongue", "pulse", "palpitation_timing", "sleep_quality", "anxiety"],
    "心系_失眠": ["tongue", "pulse", "sleep_onset", "dream_quality", "fatigue"],
    "肝膽_脅痛": ["tongue", "pulse", "pain_location", "emotional_state", "bitter_taste"],
    "腎系_腰痛": ["tongue", "pulse", "pain_nature", "urination", "sexual_function"],
    "default": ["tongue", "pulse", "cold_heat", "chief_complaint"]  # 通用預設
}

# 鑑別鍵 (用於 StageDecider)
DIFFERENTIAL_KEYS = ["cold_heat", "sweating", "thirst", "sore_throat", "phlegm_color", "stool"]


# === PSS Models ===
class SyndromeCandidate(BaseModel):
    """候選症候"""
    syndrome: str
    weight: float  # 0.0 - 1.0


class SelectedSyndrome(BaseModel):
    """已選定的暫定症候"""
    syndrome: str
    confidence: float  # 0.0 - 1.0


class ProvisionalSyndromeState(BaseModel):
    """暫定症候狀態 (PSS) - 每回合必須產出"""
    cluster: str                    # e.g., "肺系_外感"
    body_system: str                # e.g., "肺系"
    mode_diagnosis: str             # e.g., "感冒" (WarRoomAnalyzer 眾數)
    candidates: List[SyndromeCandidate]
    selected: SelectedSyndrome
    evidence: List[str]             # 已獲得的辨證鍵
    missing_keys: List[str]         # 缺失的辨證鍵
    stage: Literal["ask_more", "retrieve_and_repair", "finalize"]
    turn_index: int
    
    class Config:
        extra = "allow"


# === Stage Enum ===
class DiagnosisStage(str, Enum):
    ASK_MORE = "ask_more"
    RETRIEVE_AND_REPAIR = "retrieve_and_repair"
    FINALIZE = "finalize"


# === Helper Functions ===

def determine_stage(
    features: Dict[str, Any], 
    cluster: str = "default",
    turn_type: str = "NORMAL"  # [V3.1.1 Phase 2D] 新增：回合類型
) -> str:
    """
    StageDecider: Orchestrator 決定 stage，LLM 不得決定
    
    [V3.1.1 Phase 2D] 支援 SUPPLEMENT 回合：
    - SUPPLEMENT: 本輪只補舌脈，但累積池已有主訴/症狀 → 允許檢索
    - NORMAL: 原有邏輯
    
    finalize: 主訴存在 + (舌或脈至少一項) + 鑑別鍵 >= 1
    retrieve_and_repair: 主訴存在，但舌脈不足或鑑別鍵不足
    ask_more: 主訴都不穩或症狀太少
    """
    has_tongue = bool(features.get("tongue"))
    has_pulse = bool(features.get("pulse"))
    has_chief_complaint = bool(features.get("chief_complaint"))
    
    # 鑑別鍵檢查
    diff_count = sum(1 for k in DIFFERENTIAL_KEYS if features.get(k))
    
    # [V3.1.1 Phase 2D] SUPPLEMENT 回合允許檢索（即使本輪只補舌脈）
    if turn_type == "SUPPLEMENT":
        # 本輪只補舌脈，但累積池已有主訴/症狀
        # → 允許檢索，更新暫定診斷
        if has_chief_complaint and (has_tongue or has_pulse):
            if diff_count >= 1:
                return DiagnosisStage.FINALIZE.value  # 有鑑別鍵 → 最終診斷
            else:
                return DiagnosisStage.RETRIEVE_AND_REPAIR.value  # 暫定診斷
    
    # [V3.1.1 Phase 2D] NORMAL 回合（原有邏輯）
    # finalize: 主訴存在 + (舌或脈至少一項) + 鑑別鍵達標
    if has_chief_complaint and (has_tongue or has_pulse) and diff_count >= 1:
        return DiagnosisStage.FINALIZE.value
    # retrieve_and_repair: 主訴存在，但舌脈不足或鑑別鍵不足
    elif has_chief_complaint:
        return DiagnosisStage.RETRIEVE_AND_REPAIR.value
    # ask_more: 主訴都不穩或症狀太少
    else:
        return DiagnosisStage.ASK_MORE.value


def calculate_missing_keys(features: Dict[str, Any], cluster: str) -> List[str]:
    """計算缺失的辨證鍵 (依 cluster)"""
    required_keys = REQUIRED_KEYS_BY_CLUSTER.get(cluster, REQUIRED_KEYS_BY_CLUSTER["default"])
    return [k for k in required_keys if not features.get(k)]


def calculate_coverage(features: Dict[str, Any], cluster: str) -> float:
    """計算覆蓋率 (依 cluster)"""
    required_keys = REQUIRED_KEYS_BY_CLUSTER.get(cluster, REQUIRED_KEYS_BY_CLUSTER["default"])
    present_keys = [k for k in required_keys if features.get(k)]
    return len(present_keys) / len(required_keys) if required_keys else 0.0


def check_consistency(features: Dict[str, Any]) -> float:
    """
    檢查特徵一致性 (是否有矛盾)
    返回 1.0 = 無矛盾, 0.0 = 嚴重矛盾
    """
    # 簡單矛盾檢測邏輯
    # 例如: 同時有 "惡寒" 和 "惡熱" 是矛盾
    contradictions = [
        ("惡寒", "惡熱"),
        ("大汗", "無汗"),
        ("便秘", "泄瀉"),
        ("口渴", "不渴"),
    ]
    
    symptoms = features.get("symptoms", [])
    if isinstance(symptoms, list):
        symptom_set = set(str(s).lower() if isinstance(s, str) else str(s.get("name", "")).lower() for s in symptoms)
    else:
        symptom_set = set()
    
    for a, b in contradictions:
        if a in symptom_set and b in symptom_set:
            return 0.5  # 發現矛盾，扣分
    
    return 1.0  # 無矛盾


def calculate_stability(prev_pss: Optional[ProvisionalSyndromeState], 
                        curr_cluster: str, 
                        curr_body_system: str,
                        analysis_mode: Optional[str] = None) -> float:
    """
    Stability 層級距離 (三段式)
    
    - 同 cluster：1.0 (同群細化，不扣分)
    - 同 body_system 或同 mode：0.7 (合理修正，輕微扣分)
    - 跨 body_system：0.0 (大幅跳動，嚴重扣分)
    """
    if prev_pss is None:
        return 1.0  # 第一輪，完全穩定
    
    if prev_pss.cluster == curr_cluster:
        return 1.0  # 同 cluster，不扣分
    elif prev_pss.body_system == curr_body_system:
        return 0.7  # 同 body_system，輕微扣分
    elif analysis_mode and prev_pss.mode_diagnosis == analysis_mode:
        return 0.7  # 同 mode，輕微扣分
    else:
        return 0.0  # 跨 body_system，大幅扣分


def build_pss(
    features: Dict[str, Any],
    llm_candidates: List[Dict],
    analysis: Dict[str, Any],
    prev_pss: Optional[ProvisionalSyndromeState],
    turn_index: int
) -> ProvisionalSyndromeState:
    """
    PSSBuilder: 構建 Provisional Syndrome State
    
    - confidence/missing_keys 由系統計算
    - LLM 僅提供 candidates
    """
    cluster = analysis.get("cluster", "default")
    body_system = analysis.get("body_system", cluster.split("_")[0] if "_" in cluster else cluster)
    mode_diagnosis = analysis.get("mode_diagnosis", "未知")
    
    # 計算各項指標
    missing_keys = calculate_missing_keys(features, cluster)
    coverage = calculate_coverage(features, cluster)
    consistency = check_consistency(features)
    stability = calculate_stability(prev_pss, cluster, body_system, mode_diagnosis)
    
    # 信心公式: 0.15 + 0.65*coverage + 0.15*consistency + 0.05*stability
    confidence = 0.15 + 0.65 * coverage + 0.15 * consistency + 0.05 * stability
    confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]
    
    # 解析 LLM 候選
    candidates = []
    for c in llm_candidates:
        if isinstance(c, dict):
            candidates.append(SyndromeCandidate(
                syndrome=c.get("syndrome", "未知"),
                weight=c.get("weight", 0.0)
            ))
    
    # 選擇最高權重的候選作為 selected
    if candidates:
        top_candidate = max(candidates, key=lambda x: x.weight)
        selected = SelectedSyndrome(syndrome=top_candidate.syndrome, confidence=confidence)
    else:
        selected = SelectedSyndrome(syndrome="待釐清", confidence=confidence)
    
    # 收集證據
    evidence = [k for k in REQUIRED_KEYS_BY_CLUSTER.get(cluster, []) if features.get(k)]
    
    # 決定 stage
    stage = determine_stage(features, cluster)
    
    return ProvisionalSyndromeState(
        cluster=cluster,
        body_system=body_system,
        mode_diagnosis=mode_diagnosis,
        candidates=candidates,
        selected=selected,
        evidence=evidence,
        missing_keys=missing_keys,
        stage=stage,
        turn_index=turn_index
    )


def is_anchor_valid(candidate: Dict[str, Any], 
                    current_pss: ProvisionalSyndromeState, 
                    analysis: Dict[str, Any]) -> bool:
    """
    Anchor 同群 Gating (同層級比較)
    
    降級 anchor 必須符合同 cluster / body_system / mode_diagnosis
    mode 比 mode，不跨層級
    """
    return (
        candidate.get("cluster") == current_pss.cluster or
        candidate.get("body_system") == current_pss.body_system or
        candidate.get("mode_diagnosis") == analysis.get("mode_diagnosis")
    )


def build_fallback_pss(turn_index: int) -> ProvisionalSyndromeState:
    """
    Extractor Fail 保底: 產出最低信心 PSS
    """
    return ProvisionalSyndromeState(
        cluster="未知",
        body_system="未知",
        mode_diagnosis="未知",
        candidates=[],
        selected=SelectedSyndrome(syndrome="待釐清", confidence=0.15),
        evidence=[],
        missing_keys=["chief_complaint", "tongue", "pulse"],
        stage="ask_more",
        turn_index=turn_index
    )
