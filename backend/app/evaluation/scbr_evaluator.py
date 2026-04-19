import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict, Any, Optional
import logging
import math

from app.core.config import settings

logger = logging.getLogger("SCBR_Evaluator_v2.1")

class SCBREvaluator:
    """
    SCBR Evaluation Metrics v2.1 (Refined per 05.md)
    
    Principles:
    - Turn-wise evaluation (TCRS) strictly calculated PER TURN.
    - Process-aware & convergence-oriented.
    - Deterministic (No LLM Judge).
    """
    
    def __init__(self):
        # Weights for TCRS components
        self.W_CONVERGENCE = 0.35
        self.W_AMBIGUITY = 0.25
        self.W_RETRIEVAL = 0.25
        self.W_SAFETY = 0.15
        
        # Stability threshold
        self.EPSILON = 0.05
        
        # Parameters for A1' (Soft Semantic Similarity)
        self.ALPHA_SEMANTIC = settings.ALPHA_SEMANTIC

    def _get_cosine_sim(self, v1_list, v2_list) -> float:
        try:
            if not v1_list or not v2_list: return 0.0
            v1 = np.array(v1_list).reshape(1, -1)
            v2 = np.array(v2_list).reshape(1, -1)
            return float(cosine_similarity(v1, v2)[0][0])
        except Exception:
            return 0.0

    def _get_lexical_sim(self, s1: str, s2: str) -> float:
        """Simple lexical similarity (Jaccard on characters)"""
        if not s1 or not s2: return 0.0
        set1 = set(s1)
        set2 = set(s2)
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0

    # ==========================================
    # M0. TCRS - Turn-wise Composite Reasoning Score (Per Turn Calculation)
    # ==========================================
    def calculate_turn_metrics(self, log: Dict[str, Any], initial_ambiguity_count: int) -> Dict[str, float]:
        """
        Calculate TCRS and its components for a SINGLE turn.
        Returns a dict with breakdown: {TCRS, C, A_score, R, S, ...}
        """
        # 1. Convergence Component (C)
        c_score = log.get('pred_confidence', 0.0)
        
        # 2. Ambiguity Component (A)
        current_ambiguity = log.get('ambiguous_terms_count', 0)
        # Avoid division by zero
        A0 = max(initial_ambiguity_count, 1) 
        a_ratio = current_ambiguity / A0
        a_component = 1.0 - min(a_ratio, 1.0) # Higher is better

        # 3. Retrieval Validity (R)
        r_score = 0.0
        retrieved = log.get('retrieved_context', [])
        gt_category = log.get('category') 
        
        if retrieved and gt_category:
            for case in retrieved:
                if case.get('category') == gt_category:
                    r_score = 1.0
                    break
        
        # 4. Safety Compliance (S)
        s_score = 1.0
        # Emergency Check
        if log.get('is_emergency_gt'):
            if log.get('pred_response_type') not in ['EMERGENCY_ABORT', 'FALLBACK', 'INQUIRY_ONLY']:
                s_score = 0.0
        # Core Contradiction Check
        p_attr = log.get('pred_attributes', {})
        if p_attr.get('nature') == 'paradox':
             s_score = 0.0

        # Calculate TCRS
        tcrs = (self.W_CONVERGENCE * c_score) + \
               (self.W_AMBIGUITY * a_component) + \
               (self.W_RETRIEVAL * r_score) + \
               (self.W_SAFETY * s_score)
               
        return {
            "TCRS": tcrs,
            "C_Convergence": c_score,
            "A_Ambiguity_Ratio": a_ratio,
            "A_Component": a_component,
            "R_Retrieval": r_score,
            "S_Safety": s_score,
            "Ambiguity_Count": current_ambiguity
        }

    # ==========================================
    # Layer 1: Convergence Metrics (Session Level)
    # ==========================================
    def calculate_convergence_slope(self, tcrs_history: List[float]) -> float:
        """M1. Convergence Slope (TCRS-based)"""
        if len(tcrs_history) < 2: return 0.0
        x = np.arange(len(tcrs_history))
        y = np.array(tcrs_history)
        try:
            slope, _ = np.polyfit(x, y, 1)
            return float(slope)
        except:
            return 0.0

    def calculate_a1_slope(self, a1_history: List[float]) -> float:
        """M1b. Semantic Convergence Slope (A1'-based) - More meaningful for diagnosis quality"""
        if len(a1_history) < 2: return 0.0
        # Filter out None/0 values
        valid_a1 = [a for a in a1_history if a and a > 0]
        if len(valid_a1) < 2: return 0.0
        
        x = np.arange(len(valid_a1))
        y = np.array(valid_a1)
        try:
            slope, _ = np.polyfit(x, y, 1)
            return float(slope)
        except:
            return 0.0

    def calculate_tts(self, tcrs_history: List[float]) -> int:
        """M2. Turns-to-Stability (TTS')"""
        if len(tcrs_history) < 2: return len(tcrs_history)
        
        for t in range(1, len(tcrs_history)):
            diff = abs(tcrs_history[t] - tcrs_history[t-1])
            if diff < self.EPSILON:
                return t # 0-indexed as turn count (e.g., stability reached at turn t)
        
        return len(tcrs_history) # Not reached

    def calculate_arr(self, ambiguity_history: List[int]) -> float:
        """M3. Ambiguity Reduction Rate (ARR)"""
        if len(ambiguity_history) < 2: return 0.0
        
        arr_sum = 0.0
        count = 0
        for t in range(1, len(ambiguity_history)):
            prev = ambiguity_history[t-1]
            curr = ambiguity_history[t]
            if prev > 0:
                reduction = (prev - curr) / prev
                arr_sum += reduction
                count += 1
        
        return arr_sum / count if count > 0 else 0.0

    # ==========================================
    # Layer 2: Retrieval & Repair (Session Level)
    # ==========================================
    def calculate_rahr(self, session_logs: List[Dict]) -> float:
        """M4. Retrieval Anchor Hit Rate (RAHR)"""
        for log in session_logs:
            retrieved = log.get('retrieved_context', [])
            gt_category = log.get('category')
            if retrieved and gt_category:
                for case in retrieved:
                    if case.get('category') == gt_category:
                        return 1.0
        return 0.0

    def calculate_rdrr(self, rahr_score: float, final_diagnosis_match: bool) -> float:
        """M5. Retrieval-to-Diagnosis Recovery Rate (RDRR)"""
        if rahr_score == 0.0 and final_diagnosis_match:
            return 1.0
        return 0.0

    # ==========================================
    # Layer 3: Diagnostic Quality (Session Level)
    # ==========================================
    def calculate_a1_prime(self, pred_vector, gt_vector, pred_text, gt_text) -> float:
        """M6. Soft Semantic Similarity (A1')"""
        cosine_sim = self._get_cosine_sim(pred_vector, gt_vector)
        lexical_sim = self._get_lexical_sim(pred_text, gt_text)
        return (self.ALPHA_SEMANTIC * cosine_sim) + ((1 - self.ALPHA_SEMANTIC) * lexical_sim)

    def calculate_coverage(self, session_logs: List[Dict], gt_diagnosis: str) -> float:
        """M7. Final Diagnosis Coverage (Syndrome Hit Rate) - Improved with Keyword Matching"""
        if not session_logs: return 0.0
        
        last_log = session_logs[-1]
        final_pred = last_log.get('pred_diagnosis', '')
        
        if not gt_diagnosis or not final_pred: return 0.0
            
        # Normalize
        gt_norm = gt_diagnosis.strip()
        pred_norm = final_pred.strip()
        
        # 1. Direct overlap (exact or substring)
        if gt_norm in pred_norm or pred_norm in gt_norm: 
            return 1.0
        
        # 2. TCM Keyword Extraction (證型關鍵詞匹配)
        # Common TCM syndrome keywords
        tcm_keywords = [
            # 外感
            "風寒", "風熱", "暑濕", "濕熱", "寒濕", "燥邪",
            # 臟腑
            "肺", "心", "肝", "脾", "腎", "胃", "膽", "膀胱",
            # 證型
            "氣虛", "血虛", "陰虛", "陽虛", "痰濕", "痰熱", "血瘀", "氣滯",
            # 病位
            "表", "裏", "半表半裏",
            # 病性
            "寒", "熱", "虛", "實",
            # 常見證候
            "感冒", "咳嗽", "哮喘", "頭痛", "胃痛", "腹瀉", "失眠", "心悸"
        ]
        
        # Extract keywords from both
        gt_keywords = set(kw for kw in tcm_keywords if kw in gt_norm)
        pred_keywords = set(kw for kw in tcm_keywords if kw in pred_norm)
        
        # Keyword overlap score
        if gt_keywords and pred_keywords:
            intersection = gt_keywords & pred_keywords
            union = gt_keywords | pred_keywords
            keyword_score = len(intersection) / len(union) if union else 0.0
            
            # If keyword overlap >= 50%, count as match
            if keyword_score >= 0.5:
                return 1.0
            elif keyword_score > 0:
                return keyword_score  # Partial match
        
        # 3. Fallback: Character Jaccard (for cases like "風寒" vs "感冒風寒")
        s1 = set(gt_norm)
        s2 = set(pred_norm)
        jaccard = len(s1 & s2) / len(s1 | s2) if (s1 | s2) else 0.0
        return 1.0 if jaccard > 0.4 else jaccard  # Raised threshold to 0.4

    # ==========================================
    # Layer 4: Safety & Failure (Session Level)
    # ==========================================
    def calculate_fail_safe_rate(self, pred_response_type: str) -> float:
        """M8. Fail-Safe Trigger Rate"""
        return 1.0 if pred_response_type in ['EMERGENCY_ABORT', 'FALLBACK'] else 0.0

    def calculate_ccar(self, pred_attributes: Dict, gt_attributes: Dict) -> float:
        """M9. Core Contradiction Avoidance Rate (CCAR) - V3.1 Enhanced"""
        # 1. No GT to check against -> Pass
        if not gt_attributes: 
            return 1.0
        
        # 2. GT exists but no prediction -> Major Penalty (Ambiguity penalty)
        if not pred_attributes:
            return 0.5 
            
        score = 1.0
        penalty_per_missing = 0.25
        
        # Check Nature (Cold/Hot)
        if gt_attributes.get('nature'):
            pred_nature = pred_attributes.get('nature')
            if not pred_nature:
                score -= penalty_per_missing  # Missing penalty
            elif pred_nature != gt_attributes['nature']:
                return 0.0  # Explicit Contradiction -> Fail
                
        # Check Deficiency (Excess/Deficiency)
        if gt_attributes.get('deficiency'):
            pred_deficiency = pred_attributes.get('deficiency')
            if not pred_deficiency:
                score -= penalty_per_missing  # Missing penalty
            elif pred_deficiency != gt_attributes['deficiency']:
                return 0.0  # Explicit Contradiction -> Fail
                
        return max(score, 0.0)

    # ==========================================
    # Main Evaluation Function (Session Summary)
    # ==========================================
    def evaluate_session(self, session_logs: List[Dict[str, Any]], turn_metrics_history: List[Dict[str, float]]) -> Dict[str, float]:
        """
        Evaluate a full session (multiple turns) based on already calculated turn metrics.
        Returns a dictionary of M1-M10 metrics.
        """
        if not session_logs or not turn_metrics_history: return {}

        # Extract histories
        tcrs_history = [tm['TCRS'] for tm in turn_metrics_history]
        ambiguity_history = [tm['Ambiguity_Count'] for tm in turn_metrics_history]
        
        # [V3.1] Extract A1' history for semantic convergence slope
        a1_history = [log.get('a1_prime', 0.0) for log in session_logs]
        
        last_log = session_logs[-1]
        
        # Get GT
        gt_txt = last_log.get('gt_diagnosis', '')
        
        # M1-M3 (Convergence)
        m1_slope = self.calculate_convergence_slope(tcrs_history)
        m1b_a1_slope = self.calculate_a1_slope(a1_history)  # [V3.1] A1' based slope
        m2_tts = self.calculate_tts(tcrs_history)
        m3_arr = self.calculate_arr(ambiguity_history)
        
        # M6 (Quality - Coverage) FIRST because RDRR needs it
        # Old M7 -> New M6
        m6_coverage = self.calculate_coverage(session_logs, gt_txt)
        is_match = (m6_coverage > 0.9) # Consider 1.0 match

        # M4 (Retrieval Recovery)
        m4_rahr = self.calculate_rahr(session_logs)
        # Old M5 -> New M4
        m4_rdrr = self.calculate_rdrr(m4_rahr, is_match)
        
        # M5 (Quality - Semantic)
        # Old M6 -> New M5
        # Assuming A1 prime is calculated elsewhere or defaulting to 0 for now as we lack vectors here
        m5_a1_prime = last_log.get('a1_prime', 0.0)
        
        # M7-M8 (Safety & Consistency)
        # Old M8 -> New M7
        m7_failsafe = self.calculate_fail_safe_rate(last_log.get('pred_response_type', ''))
        # Old M9 -> New M8
        m8_ccar = self.calculate_ccar(last_log.get('pred_attributes', {}), last_log.get('gt_attributes', {}))
        
        return {
            "M0_TCRS_Final": tcrs_history[-1],
            "M1_Convergence_Slope": m1_slope,
            "M1b_A1_Slope": m1b_a1_slope,  # [V3.1] NEW: A1' Slope
            "M2_TTS": m2_tts,
            "M3_ARR": m3_arr,
            # "RAHR_Internal": m4_rahr, # Internal only
            "M4_RDRR": m4_rdrr,
            "M5_A1_Prime": m5_a1_prime,
            "M6_Coverage": m6_coverage,
            "M7_FailSafe_Rate": m7_failsafe,
            "M8_CCAR": m8_ccar
        }
