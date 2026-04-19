import logging
from typing import Dict, Any, Union
from app.api.schemas import UnifiedResponse, ResponseType
from opencc import OpenCC

logger = logging.getLogger(__name__)

class OutputGuard:
    """
    規格書 5.2 輸出端防護
    1. LLM05 (輸出處理): JSON Schema 驗證
    2. LLM09 (錯誤資訊): 證據追溯檢查 (Evidence Trace Check)
    3. 語言規範: 強制轉繁體中文 (OpenCC)
    """
    
    # 初始化 OpenCC (簡體到繁體)
    cc = OpenCC('s2t')

    @staticmethod
    def validate_structure(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        驗證 LLM 輸出的 JSON 是否包含必要欄位 (Dict Mode)。
        """
        required_fields = ["response_type", "diagnosis_list", "evidence_trace"]
        
        try:
            missing = [f for f in required_fields if f not in data]
            if missing:
                logger.error(f"[OutputGuard] Missing required fields in LLM output: {missing}")
                if "evidence_trace" not in data:
                    data["evidence_trace"] = "警告：系統未能生成完整推導過程 (Missing Trace)"
                if "diagnosis_list" not in data:
                    data["diagnosis_list"] = []
                if "response_type" not in data:
                    data["response_type"] = "FALLBACK"
            
            # Evidence Trace Check
            if not data.get("evidence_trace") or len(data["evidence_trace"]) < 5:
                logger.warning("[OutputGuard] Evidence trace is empty or too short. Intercepting.")
                data["evidence_trace"] = "警告：系統偵測到推導證據不足，請醫師謹慎參考。"
                data["response_type"] = "FALLBACK"

            return data

        except Exception as e:
            logger.error(f"[OutputGuard] Validation Logic Error: {str(e)}")
            return {
                "response_type": "FALLBACK",
                "diagnosis_list": [],
                "evidence_trace": "System Error in Output Guard"
            }

    @classmethod
    def validate_response(cls, response: UnifiedResponse) -> UnifiedResponse:
        """
        驗證 Pydantic Model 輸出 (Object Mode)。
        用於 Orchestrator 最終檢查。
        """
        try:
            # 1. 語言轉碼 (Simplified -> Traditional)
            if response.evidence_trace:
                response.evidence_trace = cls.cc.convert(response.evidence_trace)
            
            if response.formatted_report:
                response.formatted_report = cls.cc.convert(response.formatted_report)
                
            if response.safety_warning:
                response.safety_warning = cls.cc.convert(response.safety_warning)
                
            if response.follow_up_question and response.follow_up_question.question_text:
                response.follow_up_question.question_text = cls.cc.convert(response.follow_up_question.question_text)
                response.follow_up_question.options = [cls.cc.convert(opt) for opt in response.follow_up_question.options]
                
            if response.diagnosis_list:
                for diag in response.diagnosis_list:
                    diag.disease_name = cls.cc.convert(diag.disease_name)
                    if diag.condition:
                        diag.condition = cls.cc.convert(diag.condition)

            # 2. Evidence Trace Check (LLM09)
            if not response.evidence_trace or len(response.evidence_trace) < 10:
                logger.warning("[OutputGuard] Evidence trace too short in UnifiedResponse. Downgrading confidence.")
                response.evidence_trace += " [警告: 推導過程過短，請謹慎判讀]"
                response.response_type = ResponseType.FALLBACK

            # 3. Logical Consistency Check
            # 若說是 DEFINITIVE，卻沒有診斷結果 -> 強制轉 FALLBACK
            if response.response_type == ResponseType.DEFINITIVE and not response.diagnosis_list:
                logger.warning("[OutputGuard] Inconsistent response: DEFINITIVE but no diagnosis. Fixing.")
                response.response_type = ResponseType.FALLBACK
                response.evidence_trace += " [系統修正: 無診斷結果，轉為 FALLBACK]"

            # 4. Safety Warning Injection (Optional)
            # 可在此處統一加入免責聲明
            
            return response

        except Exception as e:
            logger.error(f"[OutputGuard] Model Validation Error: {str(e)}")
            # Fail safe: Return original or a safe fallback
            return response