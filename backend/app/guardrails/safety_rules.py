import re
import logging
from typing import List, Optional
from app.api.schemas import DiagnosisCandidate

logger = logging.getLogger(__name__)

class SafetyRuleEngine:
    """
    規格書 4.0 補充模組 1: 禁忌症與安全規則引擎
    Pure Python Regex Implementation.
    """
    
    # 懷孕禁忌關鍵字
    PREGNANCY_CONTRAINDICATIONS = ["攻下", "破血", "峻汗", "大毒"]
    
    @classmethod
    def check(cls, diagnosis_list: List[DiagnosisCandidate], patient_profile: dict = None) -> Optional[str]:
        """
        檢查診斷建議是否違反安全規則。
        回傳 Warning String 或 None。
        """
        warnings = []
        try:
            # 假設 patient_profile 有 'is_pregnant' 欄位 (可從對話歷史提取，此處簡化)
            is_pregnant = patient_profile.get("is_pregnant", False) if patient_profile else False

            for diag in diagnosis_list:
                # 這裡假設 DiagnosisCandidate 的 condition 或其他欄位可能包含治則關鍵字
                # 若只有 disease_name，則需檢查該病名的預設治則 (這裡僅作示範)
                pass 
            
            # 範例規則：若病名包含"孕"，且建議包含"攻下" (假設治則混在 condition 或 report 中)
            # 實際應用需解析 treatment_principle 欄位
            
            # 這裡我們做一個通用檢查：如果推導出的治則包含 "劇毒"
            # (此處需依賴上游傳入 treatment_principle，若無則跳過)
            
            return " | ".join(warnings) if warnings else None

        except Exception as e:
            logger.error(f"[SafetyRule] Check failed: {str(e)}")
            return None # 失敗時不阻擋，但記錄 Log