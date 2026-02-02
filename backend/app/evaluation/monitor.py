import logging
import time
import math
from typing import Dict, Any, List
from app.api.schemas import WorkflowState
from app.evaluation.scbr_evaluator import SCBREvaluator

logger = logging.getLogger("monitoring")

class MonitorService:
    """
    規格書 6.3: 線上監控 (Online Monitoring)
    負責記錄系統運作指標：回應時間、Token 使用量、使用者反饋。
    [V2.1 Update] Integrates with SCBREvaluator for TCRS calculation (Online Mode).
    """
    
    def __init__(self):
        self.evaluator = SCBREvaluator()

    @staticmethod
    def log_latency(session_id: str, endpoint: str, start_time: float):
        """
        記錄 API 延遲
        """
        latency_ms = (time.time() - start_time) * 1000
        logger.info(f"[METRIC] Type=Latency | Session={session_id} | Endpoint={endpoint} | Value={latency_ms:.2f}ms")

    @staticmethod
    def log_token_usage(session_id: str, prompt_tokens: int, completion_tokens: int):
        """
        記錄 Token 消耗 (成本監控)
        """
        total_tokens = prompt_tokens + completion_tokens
        logger.info(f"[METRIC] Type=TokenUsage | Session={session_id} | Total={total_tokens} | Prompt={prompt_tokens} | Completion={completion_tokens}")

    @staticmethod
    def log_feedback_score(session_id: str, feedback_action: str):
        """
        記錄使用者滿意度 (CSAT Proxy)
        """
        score_map = {"ACCEPT": 5, "MODIFY": 3, "REJECT": 1}
        score = score_map.get(feedback_action, 0)
        logger.info(f"[METRIC] Type=Feedback | Session={session_id} | Action={feedback_action} | Score={score}")

    def log_detailed_metrics(self, state: WorkflowState):
        """
        規格書 6.2: 紀錄詳細線上評估指標
        包含: Confidence, Path Similarity, Convergence Turns, Info Gain (Entropy)
        [V2.1] Calculate Online TCRS.
        """
        try:
            session_id = state.session_id
            
            # 1. Semantic Confidence (Top-1 Confidence)
            max_confidence = 0.0
            confidences = []
            pred_diag = ""
            
            if state.diagnosis_candidates:
                max_confidence = state.diagnosis_candidates[0].confidence
                pred_diag = state.diagnosis_candidates[0].disease_name
                confidences = [d.confidence for d in state.diagnosis_candidates]
            
            logger.info(f"[METRIC] Type=SemanticConfidence | Session={session_id} | Value={max_confidence:.4f}")

            # 2. Path Similarity (Max Similarity from Retrieval) -> Proxy for V-SCR
            max_sim = 0.0
            if state.retrieved_context:
                try:
                    # If 'similarity' is not available (e.g. from Reranker), use cross_encoder_score if normalized, or just skip
                    max_sim = max([item.get('rerank_score', 0.0) for item in state.retrieved_context], default=0.0)
                except:
                    pass
            logger.info(f"[METRIC] Type=PathSimilarity | Session={session_id} | Value={max_sim:.4f}")
            
            # 3. Path Selected
            logger.info(f"[METRIC] Type=PathSelected | Session={session_id} | Value={state.path_selected}")
            
            # 4. Convergence Turns
            logger.info(f"[METRIC] Type=TurnProcessed | Session={session_id} | Timestamp={time.time()}")

            # 5. Info Gain (Entropy)
            entropy = 0.0
            if confidences:
                total_conf = sum(confidences)
                if total_conf > 0:
                    probs = [c / total_conf for c in confidences]
                    entropy = -sum(p * math.log2(p) for p in probs if p > 0)
            logger.info(f"[METRIC] Type=InfoEntropy | Session={session_id} | Value={entropy:.4f}")

            # --- [V2.1] Online TCRS Calculation ---
            # Prepare log for Evaluator
            amb_count = 0
            pred_attributes = {}
            pred_risk = "GREEN"
            
            if state.standardized_features:
                amb_count = len(state.standardized_features.get("ambiguous_terms", []))
                pred_attributes = state.standardized_features.get("pred_attributes", {})
                pred_risk = state.standardized_features.get("risk_level", "GREEN")
            
            pred_type = "FALLBACK"
            if state.final_response:
                pred_type = state.final_response.response_type.value

            turn_data = {
                "pred_confidence": max_confidence,
                "ambiguous_terms_count": amb_count,
                # Online mode lacks GT, so Retrieval Validity (R) will be 0
                "retrieved_context": state.retrieved_context, 
                "category": None, 
                # Safety checks
                "is_emergency_gt": False, # Unknown
                "pred_response_type": pred_type,
                "pred_risk_level": pred_risk,
                "pred_attributes": pred_attributes
            }
            
            # We assume initial ambiguity is somewhat constant or we don't normalize it perfectly online
            # Passing current amb_count as initial effectively makes A component 0 change, or we pass a standard value (e.g. 5)
            # This is just an estimation.
            tcrs_result = self.evaluator.calculate_turn_metrics(turn_data, initial_ambiguity_count=5)
            online_tcrs = tcrs_result.get("TCRS", 0.0)
            
            logger.info(f"[METRIC] Type=TCRS_Online | Session={session_id} | Value={online_tcrs:.4f}")

        except Exception as e:
            logger.error(f"[Monitor] Failed to log detailed metrics: {str(e)}")

# Global Instance
monitor = MonitorService()