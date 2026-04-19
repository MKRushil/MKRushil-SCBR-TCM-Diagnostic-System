"""
QueryBuilder - 查詢構建代理
V3.1+ Perception Pipeline - Step 3

職責：
- 術語標準化 (Ontology Mapping)
- 主訴加權 (Weighting for Embedding)
- 病位推斷 (Location Inference)
"""

import logging
from typing import Dict, Any
from app.agents.base import BaseAgent
from app.prompts.perception import QUERY_BUILDER_SYSTEM_PROMPT, build_query_building_prompt
from app.prompts.base import XML_OUTPUT_INSTRUCTION

logger = logging.getLogger(__name__)


class QueryBuilder(BaseAgent):
    """
    QueryBuilder - 翻譯官
    
    執行任務：
    1. 術語標準化: 將口語化症狀映射到標準中醫術語
    2. 主訴加權: 在查詢字串中重複核心主訴（3-5次）
    3. 病位推斷: 根據症狀群推斷臟腑病位（用於 Reranker Soft Prior）
    """
    
    async def run(
        self, 
        validated_features: Dict[str, Any],
        assistant_prior: dict = None  # [V3.1.1 Phase 2E] Assistant prior（不進 query）
    ) -> Dict[str, Any]:
        """
        執行查詢構建
        
        Args:
            validated_features: FeatureValidator 驗證後的特徵
            assistant_prior: Assistant prior（用於 soft prior，不進 query）
            
        Returns:
            Dict containing weighted_query_string and primary_location
        """
        logger.info("[問題分析與加權] [QueryBuilder] 正在構建加權查詢字串...")
        
        try:
            prompt = build_query_building_prompt(validated_features)
            messages = [
                {"role": "system", "content": QUERY_BUILDER_SYSTEM_PROMPT + "\n" + XML_OUTPUT_INSTRUCTION},
                {"role": "user", "content": prompt}
            ]
            
            response_text = await self.client.generate_completion(messages, temperature=0.1)
            result = self.parse_xml_json(response_text)
            
            weighted_query = result.get('weighted_query_string', '')
            primary_location = result.get('primary_location', '未知')
            
            # [V3.1.1 Phase 2E] Query 清理：只用 user evidence
            features = validated_features.get('validated_features', {})
            symptom_query = self._build_symptom_query(features)
            
            # [V3.1.1 Phase 2E] Query 組成（debug 用）
            query_components = {
                "symptom_terms": symptom_query,
                "prior_terms": assistant_prior.get('prior_syndrome') if assistant_prior else None,
                "prior_repeat_count": 0  # Prior 不進 query
            }
            
            logger.info(f"[問題分析與加權] [QueryBuilder] 構建完成 (病位: {primary_location})")
            logger.info(f"[QueryBuilder] Query 組成: symptom_terms='{symptom_query[:40]}...', prior_terms='{query_components['prior_terms']}'")
            
            # [V3.1.1 Phase 2E] 使用清理後的 query（只含 user evidence）
            result['weighted_query_string'] = symptom_query or weighted_query
            result['query_components'] = query_components
            result['assistant_prior'] = assistant_prior  # 傳給 Reranker
            
            return result
        
        except Exception as e:
            logger.error(f"[問題分析與加權] [QueryBuilder] 構建失敗: {e}")
            # Fallback: 使用安全預設值
            features = validated_features.get('validated_features', {})
            chief_complaint_from_input = features.get('chief_complaint', '')
            symptoms_from_input = features.get('symptoms', [])
            
            # 構建一個包含預期鍵的空或默認字典
            return {
                "standardized_terms": features,
                "weighted_query_string": chief_complaint_from_input if chief_complaint_from_input else "未知症狀",
                "primary_location": None,  # 無法推斷
                "location_confidence": 0.0,
                "query_components": {},
                "assistant_prior": assistant_prior
            }
    
    def _build_symptom_query(self, features: dict) -> str:
        """
        構建症狀查詢字串（只用 user evidence）
        
        [V3.1.1 Phase 2E] 只包含 user 提供的症狀，不包含 prior
        """
        parts = []
        
        if features.get('chief_complaint'):
            parts.append(features['chief_complaint'])
        
        if features.get('symptoms'):
            symptoms_str = "、".join(features['symptoms'][:5])  # 限制數量
            parts.append(symptoms_str)
        
        if features.get('tongue'):
            parts.append(f"舌{features['tongue']}")
        
        if features.get('pulse'):
            parts.append(f"脈{features['pulse']}")
        
        return " ".join(parts)
