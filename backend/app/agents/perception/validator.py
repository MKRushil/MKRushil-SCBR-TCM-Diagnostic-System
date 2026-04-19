"""
FeatureValidator - 特徵驗證代理
V3.1+ Perception Pipeline - Step 2

職責：
- 上下文融合 (Context Fusion)
- 衝突解決 (Conflict Resolution)
- 互斥屬性檢查 (三層級：Hard Exclusion / Mixed / Temporal)
- 生理一致性檢查
"""

import logging
from typing import Dict, Any, List
from app.agents.base import BaseAgent
from app.prompts.perception import VALIDATOR_SYSTEM_PROMPT, build_validation_prompt
from app.prompts.base import XML_OUTPUT_INSTRUCTION

logger = logging.getLogger(__name__)


class FeatureValidator(BaseAgent):
    """
    FeatureValidator - 預處理器
    
    執行任務：
    1. 上下文融合: 將本輪症狀與歷史對話合併
    2. 衝突解決: 若新舊資訊衝突，採用「最新資訊優先」
    3. 互斥屬性檢查: 識別邏輯矛盾（三層級）
    4. 生理一致性檢查: 確認症狀符合性別、年齡
    """
    
    async def run(
        self,
        raw_symptoms: Dict[str, Any],
        session_history: List[Dict] = None,
        patient_profile: Dict[str, Any] = None,
        cumulative_features: dict = None,   # [V3.1.1 Phase 1] 累積特徵池
        assistant_prior: dict = None        # [V3.1.1 Phase 1] Assistant prior
    ) -> Dict[str, Any]:
        """
        執行特徵驗證與融合
        
        Args:
            raw_symptoms: SymptomExtractor 提取的原始症狀
            session_history: 對話歷史紀錄
            patient_profile: 患者背景（性別、年齡）
            cumulative_features: 累積特徵池（session-level）
            assistant_prior: Assistant 的 prior（不進 symptoms）
            
        Returns:
            Dict containing validated features
        """
        if session_history is None:
            session_history = []
        
        if patient_profile is None:
            patient_profile = {"gender": "未知", "age": "未知"}
        
        if cumulative_features is None:
            cumulative_features = {}
        
        logger.info("[問題分析與加權] [FeatureValidator] 正在進行特徵驗證與上下文融合...")
        
        try:
            prompt = build_validation_prompt(raw_symptoms, session_history, patient_profile)
            messages = [
                {"role": "system", "content": VALIDATOR_SYSTEM_PROMPT + "\n" + XML_OUTPUT_INSTRUCTION},
                {"role": "user", "content": prompt}
            ]
            
            response_text = await self.client.generate_completion(messages, temperature=0.1)
            result = self.parse_xml_json(response_text)
            
            # [V3.1.1 Phase 1] 欄位拆分：symptoms[] vs prior_syndrome
            validated_features = result.get('validated_features', {})
            
            # [V3.1.1 Phase 1] 輸出污染隔離：assistant 輸出不得進 symptoms[]
            # 證名硬隔離（雙重防線）
            validated_symptoms = validated_features.get('symptoms', [])
            validated_features['symptoms'] = self._filter_syndrome_terms(validated_symptoms)
            
            # [V3.1.1 Phase 1] 融合改累積池（Union 合併，不覆蓋）
            if cumulative_features:
                validated_features = self._merge_cumulative(validated_features, cumulative_features)
            
            # [V3.1.1 Phase 1] 回合分類（判定 SUPPLEMENT）
            turn_type = self._classify_turn_type(validated_features, cumulative_features)
            
            # 構建返回結果
            final_result = {
                "validated_features": validated_features,
                "prior_syndrome": assistant_prior.get('prior_syndrome') if assistant_prior else None,
                "prior_confidence": assistant_prior.get('prior_confidence', 0.0) if assistant_prior else 0.0,
                "turn_type": turn_type,
                "consistency_check": result.get('consistency_check', {}),
                "biological_check": result.get('biological_check', {})
            }
            
            # [透明化] 印出累積的歷史與融合結果
            history_summary = [f"R{i+1}:{h.get('content', '')[:10]}.." for i, h in enumerate(session_history)]
            fused_symptoms = validated_features.get('symptoms', [])
            logger.info(f"[問題分析與加權] [FeatureValidator] 當前對話歷史 ({len(session_history)}輪): {history_summary}")
            logger.info(f"[問題分析與加權] [FeatureValidator] 上下文融合後症狀: {fused_symptoms}")
            logger.info(f"[FeatureValidator] 特徵分解: symptoms_from_user={len(fused_symptoms)}, prior_from_assistant={assistant_prior.get('prior_syndrome') if assistant_prior else 'None'}, turn_type={turn_type}")
            
            # 記錄一致性檢查結果
            consistency = result.get('consistency_check', {})
            status = consistency.get('status', 'PASS')
            details = consistency.get('details', '無')
            
            if status == 'LOGICAL_PARADOX':
                logger.warning(f"[問題分析與加權] [FeatureValidator] 發現邏輯矛盾: {details}")
            elif status == 'MIXED_PATTERN':
                logger.info(f"[問題分析與加權] [FeatureValidator] 發現錯雜證型: {details}")
            else:
                logger.info(f"[問題分析與加權] [FeatureValidator] 邏輯檢核通過 ({status})")
            
            return final_result
        
        except Exception as e:
            logger.error(f"[問題分析與加權] [FeatureValidator] 驗證過程發生錯誤: {e}")
            # Fallback: 返回最小化結構
            return {
                "validated_features": raw_symptoms.get('raw_symptoms_extracted', {}),
                "consistency_check": {"status": "ERROR", "details": str(e)},
                "biological_check": {"gender_consistent": True, "age_consistent": True},
                "turn_type": "NORMAL"
            }
    
    # ==================== V3.1.1 Helper Functions (Phase 1) ====================
    
    # [V3.1.1 Phase 1E] 證名/證候詞彙黑名單
    SYNDROME_KEYWORDS = {
        # 證候類型
        "證", "型", "症候", "證候",
        # 常見證名片段
        "氣滯", "血瘀", "痰濕", "陰虛", "陽虛", "氣虛", "血虛",
        "風寒", "風熱", "濕熱", "寒濕", "痰熱", "痰濕",
        "肝鬱", "脾虛", "腎虛", "心火", "肺熱",
        # 疾病名稱（不應出現在 symptoms）
        "感冒", "頭痛", "胸痺", "痛經", "濕疹", "咳嗽"
    }
    
    def _filter_syndrome_terms(self, symptoms: List[str]) -> List[str]:
        """
        過濾證名/證候詞彙（硬隔離保險）
        
        規則:
        - 包含「證」、「型」的詞彙 → 移除
        - 包含證候關鍵字的複合詞 → 移除
        - 疾病名稱 → 移除
        """
        filtered = []
        removed = []
        
        for symptom in symptoms:
            # 規則 1: 包含「證」、「型」
            if "證" in symptom or "型" in symptom:
                removed.append(symptom)
                continue
            
            # 規則 2: 包含證候關鍵字
            if any(kw in symptom for kw in self.SYNDROME_KEYWORDS):
                removed.append(symptom)
                continue
            
            # 規則 3: 疾病名稱（完全匹配）
            if symptom in self.SYNDROME_KEYWORDS:
                removed.append(symptom)
                continue
            
            filtered.append(symptom)
        
        if removed:
            logger.warning(f"[FeatureValidator] 證名硬隔離: 移除 {removed}")
        
        return filtered
    
    def _merge_cumulative(self, current: dict, cumulative: dict) -> dict:
        """
        累積池合併（Union + 去重）
        
        規則:
        - 主訴: 不覆蓋（current or cumulative）
        - 症狀: Union 合併（去重）
        - 舌脈: 新值覆蓋舊值（更新）
        """
        merged = cumulative.copy()
        
        # 主訴繼承（不歸零）
        if current.get('chief_complaint'):
            merged['chief_complaint'] = current['chief_complaint']
        
        # 症狀 Union
        current_symptoms = set(current.get('symptoms', []))
        cumulative_symptoms = set(cumulative.get('symptoms', []))
        merged['symptoms'] = list(current_symptoms | cumulative_symptoms)
        
        # 舌脈更新
        if current.get('tongue'):
            merged['tongue'] = current['tongue']
        if current.get('pulse'):
            merged['pulse'] = current['pulse']
        
        logger.info(f"[FeatureValidator] 累積合併: 症狀 {len(cumulative_symptoms)} → {len(merged['symptoms'])}")
        
        return merged
    
    def _classify_turn_type(self, current: dict, cumulative: dict) -> str:
        """
        分類回合類型
        
        NORMAL: 本輪有主訴或症狀
        SUPPLEMENT: 本輪只補舌脈（前面已有主訴/症狀）
        """
        has_current_chief = bool(current.get('chief_complaint'))
        has_current_symptoms = bool(current.get('symptoms'))
        has_current_tongue_pulse = bool(current.get('tongue') or current.get('pulse'))
        
        has_cumulative_chief = bool(cumulative and cumulative.get('chief_complaint'))
        has_cumulative_symptoms = bool(cumulative and cumulative.get('symptoms'))
        
        # SUPPLEMENT: 本輪只有舌脈，但累積池有主訴/症狀
        if (not has_current_chief and not has_current_symptoms and has_current_tongue_pulse
            and (has_cumulative_chief or has_cumulative_symptoms)):
            return "SUPPLEMENT"
        
        return "NORMAL"
